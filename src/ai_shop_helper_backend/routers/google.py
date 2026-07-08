import secrets
import urllib.parse
from uuid import UUID

import jwt
from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core import security as _security
from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.deps import CurrentUser, SessionDep
from ai_shop_helper_backend.models.auth import RefreshToken
from ai_shop_helper_backend.schemas.auth import Token
from ai_shop_helper_backend.schemas.google import (
    GA4RealtimeRequest,
    GA4ReportRequest,
    GoogleCallbackSuccess,
    GoogleConnectResponse,
    GoogleStatusResponse,
    SearchConsoleQueryRequest,
)
from ai_shop_helper_backend.services import google as google_svc
from ai_shop_helper_backend.services import users as users_svc

router = APIRouter(prefix="/google", tags=["google"])

_STATE_EXPIRY_MINUTES = 10
_OAUTH_STATE_COOKIE = "oauth_state"


def _create_state_token(mode: str, user_id: UUID | None = None) -> str:
    from datetime import timedelta

    from ai_shop_helper_backend.core.utils import get_datetime_utc

    now = get_datetime_utc()
    payload: dict = {
        "mode": mode,
        "nonce": secrets.token_urlsafe(8),
        "exp": now + timedelta(minutes=_STATE_EXPIRY_MINUTES),
    }
    if user_id is not None:
        payload["user_id"] = str(user_id)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.KEY_ALGORITHM)


def _decode_state_token(state: str) -> dict:
    try:
        return jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.KEY_ALGORITHM])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )


def _set_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=_STATE_EXPIRY_MINUTES * 60,
    )


async def _issue_tokens(session: AsyncSession, response: Response, user_id: UUID) -> Token:
    user = await users_svc.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    refresh_token_value = _security.generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token=refresh_token_value,
            expires_at=_security.refresh_token_expiry(),
        )
    )
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE,
        value=refresh_token_value,
        httponly=True,
        secure=True,
        samesite="strict",
        path=settings.refresh_token_path,
    )
    return Token(
        access_token=_security.create_access_token(str(user_id), user.is_superuser)
    )


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.get("/login", response_model=GoogleConnectResponse)
async def login_with_google(response: Response) -> GoogleConnectResponse:
    """Generate the Google OAuth URL for login/registration (no existing account needed)."""
    state = _create_state_token(mode="login")
    _set_state_cookie(response, state)
    return GoogleConnectResponse(auth_url=google_svc.build_auth_url(state, scopes=google_svc.LOGIN_SCOPES))


@router.get("/connect", response_model=GoogleConnectResponse)
async def connect_google(current_user: CurrentUser, response: Response) -> GoogleConnectResponse:
    """Generate the Google OAuth URL to link Google to an existing account."""
    state = _create_state_token(mode="connect", user_id=current_user.id)
    _set_state_cookie(response, state)
    return GoogleConnectResponse(auth_url=google_svc.build_auth_url(state))


@router.get("/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    session: SessionDep,
    response: Response,
) -> GoogleCallbackSuccess | Token:
    """OAuth2 callback — Google redirects here after user grants access.

    Handles two modes encoded in the state JWT:
    - connect: links Google to an existing authenticated user
    - login: registers or logs in a user via Google
    """
    stored_state = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not stored_state or stored_state != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )
    response.delete_cookie(_OAUTH_STATE_COOKIE)

    state_payload = _decode_state_token(state)
    mode = state_payload.get("mode", "connect")

    try:
        token_data = await google_svc.exchange_code(code)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange authorization code with Google",
        )

    access_token = token_data["access_token"]
    google_refresh_token = token_data.get("refresh_token")
    if not google_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return a refresh token. Try revoking access and reconnecting.",
        )

    try:
        userinfo = await google_svc.get_userinfo(access_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch Google user info",
        )

    google_id = userinfo["sub"]
    google_email = userinfo["email"]
    expires_in = int(token_data.get("expires_in", 3600))
    scopes = token_data.get("scope", "")

    if mode == "connect":
        user_id = UUID(state_payload["user_id"])

        existing = await google_svc.get_credentials_by_google_id(session, google_id)
        if existing and existing.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Google account is already linked to another user",
            )

        await google_svc.upsert_credentials(
            session=session,
            user_id=user_id,
            google_id=google_id,
            google_email=google_email,
            access_token=access_token,
            refresh_token=google_refresh_token,
            expires_in=expires_in,
            scopes=scopes,
        )
        return GoogleCallbackSuccess(
            message="Google account connected successfully",
            google_email=google_email,
        )

    # login mode: find existing user by google_id, then by email, or create new
    if not userinfo.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account email is not verified",
        )

    credential = await google_svc.get_credentials_by_google_id(session, google_id)
    if credential:
        user_id = credential.user_id
    else:
        user = await users_svc.get_user_by_email(session, google_email)
        if not user:
            user = await users_svc.create_google_user(
                session,
                name=userinfo.get("name", google_email),
                email=google_email,
            )
            await session.flush()
        user_id = user.id

    await google_svc.upsert_credentials(
        session=session,
        user_id=user_id,
        google_id=google_id,
        google_email=google_email,
        access_token=access_token,
        refresh_token=google_refresh_token,
        expires_in=expires_in,
        scopes=scopes,
    )
    return await _issue_tokens(session, response, user_id)


@router.get("/status", response_model=GoogleStatusResponse)
async def google_status(current_user: CurrentUser, session: SessionDep) -> GoogleStatusResponse:
    """Check whether the current user has a connected Google account."""
    credential = await google_svc.get_credentials(session, current_user.id)
    if not credential:
        return GoogleStatusResponse(connected=False)
    return GoogleStatusResponse(
        connected=True,
        google_email=credential.google_email,
        token_expires_at=credential.token_expires_at,
    )


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_google(current_user: CurrentUser, session: SessionDep) -> None:
    """Remove stored Google credentials and revoke the token in Google."""
    credential = await google_svc.get_credentials(session, current_user.id)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Google account connected",
        )
    await google_svc.revoke_google_token(credential.refresh_token)
    await google_svc.delete_credentials(session, credential)


# ── GA4 ───────────────────────────────────────────────────────────────────────

@router.get("/ga4/accounts")
async def ga4_accounts(current_user: CurrentUser, session: SessionDep) -> dict:
    """List all GA4 accounts accessible by the connected Google account."""
    token = await _get_token(session, current_user.id)
    return await google_svc.google_get(
        token, "https://analyticsadmin.googleapis.com/v1beta/accounts"
    )


@router.get("/ga4/accounts/{account_id}/properties")
async def ga4_properties(
    account_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """List GA4 properties for an account."""
    token = await _get_token(session, current_user.id)
    return await google_svc.google_get(
        token,
        "https://analyticsadmin.googleapis.com/v1beta/properties",
        params={"filter": f"parent:accounts/{account_id}"},
    )


@router.post("/ga4/properties/{property_id}/report")
async def ga4_report(
    property_id: str,
    body: GA4ReportRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Run a GA4 Data API report."""
    token = await _get_token(session, current_user.id)
    payload: dict = {"dateRanges": body.date_ranges, "metrics": body.metrics}
    if body.dimensions:
        payload["dimensions"] = body.dimensions
    if body.limit:
        payload["limit"] = body.limit
    return await google_svc.google_post(
        token,
        f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport",
        payload,
    )


@router.post("/ga4/properties/{property_id}/realtime")
async def ga4_realtime(
    property_id: str,
    body: GA4RealtimeRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Run a GA4 Realtime report."""
    token = await _get_token(session, current_user.id)
    payload: dict = {"metrics": body.metrics}
    if body.dimensions:
        payload["dimensions"] = body.dimensions
    if body.limit:
        payload["limit"] = body.limit
    return await google_svc.google_post(
        token,
        f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runRealtimeReport",
        payload,
    )


# ── Search Console ─────────────────────────────────────────────────────────────

@router.get("/search-console/sites")
async def search_console_sites(current_user: CurrentUser, session: SessionDep) -> dict:
    """List all Search Console properties accessible by the connected Google account."""
    token = await _get_token(session, current_user.id)
    return await google_svc.google_get(
        token, "https://www.googleapis.com/webmasters/v3/sites"
    )


@router.post("/search-console/query")
async def search_console_query(
    body: SearchConsoleQueryRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Query Search Console search analytics."""
    token = await _get_token(session, current_user.id)
    encoded_url = urllib.parse.quote(body.site_url, safe="")
    return await google_svc.google_post(
        token,
        f"https://www.googleapis.com/webmasters/v3/sites/{encoded_url}/searchAnalytics/query",
        {
            "startDate": body.start_date,
            "endDate": body.end_date,
            "dimensions": body.dimensions,
            "rowLimit": body.row_limit,
        },
    )


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _get_token(session: SessionDep, user_id: UUID) -> str:
    try:
        return await google_svc.get_valid_access_token(session, user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google account not connected. Call GET /google/connect first.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to refresh Google access token",
        )
