import logging
import secrets
from datetime import timedelta
from urllib.parse import quote, urlencode
from uuid import UUID

import jwt
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.connections import google as google_conn
from ai_shop_helper_backend.connections.base import decode_secrets
from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.deps import CurrentUser, SessionDep
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.connections import ConnectionType
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.schemas.connections import (
    WordpressStartBody,
    WordpressStartResponse,
    WordpressStatusResponse,
)
from ai_shop_helper_backend.schemas.google import (
    GA4RealtimeRequest,
    GA4ReportRequest,
    GoogleConnectionStatusResponse,
    GoogleConnectResponse,
    SearchConsoleQueryRequest,
)
from ai_shop_helper_backend.services import connections as conn_service
from ai_shop_helper_backend.services import org_users, projects
from ai_shop_helper_backend.services import wordpress_tokens as wp_tokens

router = APIRouter(prefix="/connections", tags=["connections"])

logger = logging.getLogger(__name__)


async def _require_project_member(
    session: AsyncSession, current_user: User, project_id: UUID
) -> Project:
    project = await projects.get_project_by_id(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    membership = await org_users.get_org_user(session, current_user.id, project.org_id)
    if not membership and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    return project


@router.post(
    "/wordpress/{project_id}/start",
    response_model=WordpressStartResponse,
    status_code=status.HTTP_200_OK,
)
async def start_wordpress_connection(
    project_id: UUID,
    body: WordpressStartBody,
    current_user: CurrentUser,
    session: SessionDep,
) -> WordpressStartResponse:
    await _require_project_member(session, current_user, project_id)

    site_url = body.site_url.rstrip("/")
    token = await wp_tokens.create_token(session, project_id)
    await session.commit()
    await session.refresh(token)

    params = urlencode(
        {
            "page": "aishophelper-conectar",
            "token": token.token,
            "callback_url": settings.CALLBACK_API_WORDPRESS_URL,
        }
    )
    redirect_url = f"{site_url}/wp-admin/admin.php?{params}"
    return WordpressStartResponse(redirect_url=redirect_url)


@router.get("/wordpress/callback")
async def wordpress_callback(
    session: SessionDep,
    token: str = Query(...),
    app_password: str = Query(...),
    site_url: str = Query(...),
    user: str = Query(...),
) -> RedirectResponse:
    success_url = settings.WP_SUCCESS_FRONTEND_URL
    error_url = settings.WP_ERROR_FRONTEND_URL

    record = await wp_tokens.get_token(session, token)
    if not record:
        logger.error(
            "WordPress callback received invalid or already-used token: %s", token
        )
        return RedirectResponse(url=f"{error_url}?code=token_invalid")

    if wp_tokens.is_expired(record):
        logger.error("WordPress callback received expired token: %s", token)
        await wp_tokens.delete_token(session, record)
        await session.commit()
        return RedirectResponse(url=f"{error_url}?code=token_expired")

    try:
        secrets = conn_service.build_wordpress_secrets(
            site_url=site_url.rstrip("/"),
            username=user,
            app_password=app_password,
        )
        await conn_service.upsert_connection(
            session,
            project_id=record.project_id,
            connection_type=ConnectionType.wordpress,
            secrets=secrets,
        )
        await wp_tokens.delete_token(session, record)
        await session.commit()
        logger.info(
            "WordPress connection established for project %s", record.project_id
        )
        return RedirectResponse(url=success_url)
    except Exception:
        logger.exception("Unexpected error in WordPress callback")
        return RedirectResponse(url=f"{error_url}?code=error_unexpected")


@router.get(
    "/wordpress/{project_id}",
    response_model=WordpressStatusResponse,
)
async def get_wordpress_status(
    project_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> WordpressStatusResponse:
    await _require_project_member(session, current_user, project_id)

    connection = await conn_service.get_connection_by_project_and_type(
        session, project_id, ConnectionType.wordpress
    )
    if not connection:
        return WordpressStatusResponse(connected=False)

    secrets = decode_secrets(connection)
    return WordpressStatusResponse(
        connected=True,
        site_url=secrets.get("site_url"),
        username=secrets.get("username"),
    )


# ── Google (GA4 / Search Console) ───────────────────────────────────────────────

_GOOGLE_STATE_EXPIRY_MINUTES = 10
_GOOGLE_STATE_COOKIE = "oauth_connection_state"


def _create_google_state(project_id: UUID) -> str:
    now = get_datetime_utc()
    payload = {
        "project_id": str(project_id),
        "nonce": secrets.token_urlsafe(8),
        "exp": now + timedelta(minutes=_GOOGLE_STATE_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.KEY_ALGORITHM)


def _decode_google_state(state: str) -> dict | None:
    try:
        return jwt.decode(
            state, settings.SECRET_KEY, algorithms=[settings.KEY_ALGORITHM]
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


@router.get("/google/{project_id}/start", response_model=GoogleConnectResponse)
async def start_google_connection(
    project_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    response: Response,
) -> GoogleConnectResponse:
    await _require_project_member(session, current_user, project_id)

    state = _create_google_state(project_id)
    response.set_cookie(
        key=_GOOGLE_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=_GOOGLE_STATE_EXPIRY_MINUTES * 60,
    )
    return GoogleConnectResponse(auth_url=google_conn.build_auth_url(state))


@router.get("/google/callback")
async def google_connection_callback(
    code: str,
    state: str,
    request: Request,
    session: SessionDep,
) -> RedirectResponse:
    success_url = settings.WP_SUCCESS_FRONTEND_URL
    error_url = settings.WP_ERROR_FRONTEND_URL

    stored_state = request.cookies.get(_GOOGLE_STATE_COOKIE)
    if not stored_state or stored_state != state:
        return RedirectResponse(url=f"{error_url}?code=invalid_state")

    state_payload = _decode_google_state(state)
    if state_payload is None:
        return RedirectResponse(url=f"{error_url}?code=expired_state")

    try:
        token_data = await google_conn.exchange_code(code)
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            return RedirectResponse(url=f"{error_url}?code=no_refresh_token")
        userinfo = await google_conn.get_userinfo(access_token)
    except Exception:
        logger.exception("Unexpected error in Google connection callback")
        return RedirectResponse(url=f"{error_url}?code=error_unexpected")

    project_id = UUID(state_payload["project_id"])
    secrets_data = google_conn.build_secrets(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(token_data.get("expires_in", 3600)),
        scopes=token_data.get("scope", ""),
        google_email=userinfo.get("email", ""),
    )
    await conn_service.upsert_connection(
        session,
        project_id=project_id,
        connection_type=ConnectionType.google,
        secrets=secrets_data,
    )
    logger.info("Google connection established for project %s", project_id)

    redirect = RedirectResponse(url=success_url)
    redirect.delete_cookie(_GOOGLE_STATE_COOKIE)
    return redirect


@router.get(
    "/google/{project_id}",
    response_model=GoogleConnectionStatusResponse,
)
async def get_google_connection_status(
    project_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> GoogleConnectionStatusResponse:
    await _require_project_member(session, current_user, project_id)

    connection = await conn_service.get_connection_by_project(session, project_id)
    if not connection or connection.connection_type != ConnectionType.google:
        return GoogleConnectionStatusResponse(connected=False)

    secrets_data = decode_secrets(connection)
    return GoogleConnectionStatusResponse(
        connected=True, google_email=secrets_data.get("google_email")
    )


async def _get_google_token(session: SessionDep, project_id: UUID) -> str:
    try:
        return await google_conn.get_valid_access_token(session, project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google account not connected for this project.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to refresh Google access token",
        )


@router.get("/google/{project_id}/ga4/accounts")
async def ga4_accounts(
    project_id: UUID, current_user: CurrentUser, session: SessionDep
) -> dict:
    """List all GA4 accounts accessible by the project's connected Google account."""
    await _require_project_member(session, current_user, project_id)
    token = await _get_google_token(session, project_id)
    return await google_conn.google_get(
        token, "https://analyticsadmin.googleapis.com/v1beta/accounts"
    )


@router.get("/google/{project_id}/ga4/accounts/{account_id}/properties")
async def ga4_properties(
    project_id: UUID,
    account_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """List GA4 properties for an account."""
    await _require_project_member(session, current_user, project_id)
    token = await _get_google_token(session, project_id)
    return await google_conn.google_get(
        token,
        "https://analyticsadmin.googleapis.com/v1beta/properties",
        params={"filter": f"parent:accounts/{account_id}"},
    )


@router.post("/google/{project_id}/ga4/properties/{property_id}/report")
async def ga4_report(
    project_id: UUID,
    property_id: str,
    body: GA4ReportRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Run a GA4 Data API report."""
    await _require_project_member(session, current_user, project_id)
    token = await _get_google_token(session, project_id)
    payload: dict = {"dateRanges": body.date_ranges, "metrics": body.metrics}
    if body.dimensions:
        payload["dimensions"] = body.dimensions
    if body.limit:
        payload["limit"] = body.limit
    return await google_conn.google_post(
        token,
        f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport",
        payload,
    )


@router.post("/google/{project_id}/ga4/properties/{property_id}/realtime")
async def ga4_realtime(
    project_id: UUID,
    property_id: str,
    body: GA4RealtimeRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Run a GA4 Realtime report."""
    await _require_project_member(session, current_user, project_id)
    token = await _get_google_token(session, project_id)
    payload: dict = {"metrics": body.metrics}
    if body.dimensions:
        payload["dimensions"] = body.dimensions
    if body.limit:
        payload["limit"] = body.limit
    return await google_conn.google_post(
        token,
        f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runRealtimeReport",
        payload,
    )


@router.get("/google/{project_id}/search-console/sites")
async def search_console_sites(
    project_id: UUID, current_user: CurrentUser, session: SessionDep
) -> dict:
    """List all Search Console properties accessible by the project's connected Google account."""
    await _require_project_member(session, current_user, project_id)
    token = await _get_google_token(session, project_id)
    return await google_conn.google_get(
        token, "https://www.googleapis.com/webmasters/v3/sites"
    )


@router.post("/google/{project_id}/search-console/query")
async def search_console_query(
    project_id: UUID,
    body: SearchConsoleQueryRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Query Search Console search analytics."""
    await _require_project_member(session, current_user, project_id)
    token = await _get_google_token(session, project_id)
    encoded_url = quote(body.site_url, safe="")
    return await google_conn.google_post(
        token,
        f"https://www.googleapis.com/webmasters/v3/sites/{encoded_url}/searchAnalytics/query",
        {
            "startDate": body.start_date,
            "endDate": body.end_date,
            "dimensions": body.dimensions,
            "rowLimit": body.row_limit,
        },
    )
