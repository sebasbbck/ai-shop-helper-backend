import logging
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from ai_shop_helper_backend.connections.base import decode_secrets
from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.deps import CurrentUser, SessionDep
from ai_shop_helper_backend.models.connections import ConnectionType
from ai_shop_helper_backend.schemas.connections import (
    WordpressStartBody,
    WordpressStartResponse,
    WordpressStatusResponse,
)
from ai_shop_helper_backend.services import connections as conn_service
from ai_shop_helper_backend.services import org_users, projects
from ai_shop_helper_backend.services import wordpress_tokens as wp_tokens

router = APIRouter(prefix="/connections", tags=["connections"])

logger = logging.getLogger(__name__)


async def _require_project_member(session, current_user, project_id: UUID):
    project = await projects.get_project_by_id(session, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

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
        logger.error("WordPress callback received invalid or already-used token: %s", token)
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
        logger.info("WordPress connection established for project %s", record.project_id)
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

    connection = await conn_service.get_connection_by_project(session, project_id)
    if not connection:
        return WordpressStatusResponse(connected=False)

    secrets = decode_secrets(connection)
    return WordpressStatusResponse(
        connected=True,
        site_url=secrets.get("site_url"),
        username=secrets.get("username"),
    )
