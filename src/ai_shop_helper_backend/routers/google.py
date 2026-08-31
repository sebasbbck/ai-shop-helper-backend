import secrets
from datetime import timedelta

import jwt
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.deps import SessionDep
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.schemas.google import GoogleLoginResponse
from ai_shop_helper_backend.services import auth as auth_service
from ai_shop_helper_backend.services import google_auth as google_svc
from ai_shop_helper_backend.services import users as users_svc

router = APIRouter(prefix="/google", tags=["google"])

_STATE_EXPIRY_MINUTES = 10
_OAUTH_STATE_COOKIE = "oauth_login_state"


def _create_state_token() -> str:
    now = get_datetime_utc()
    payload = {
        "nonce": secrets.token_urlsafe(8),
        "exp": now + timedelta(minutes=_STATE_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.KEY_ALGORITHM)


def _is_valid_state_token(state: str) -> bool:
    try:
        jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.KEY_ALGORITHM])
        return True
    except (jwt.PyJWTError, ValueError, KeyError):
        return False


@router.get("/login", response_model=GoogleLoginResponse)
async def login_with_google(response: Response) -> GoogleLoginResponse:
    """Generate the Google OAuth URL for login/registration."""
    state = _create_state_token()
    response.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=_STATE_EXPIRY_MINUTES * 60,
    )
    return GoogleLoginResponse(auth_url=google_svc.build_auth_url(state))


@router.get("/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    session: SessionDep,
) -> RedirectResponse:
    """OAuth2 callback — Google redirects here after the user grants access.

    Always redirects to the frontend (success or error), never returns JSON —
    the refresh cookie set on success is enough for the frontend to bootstrap
    a session via the existing /auth/refresh.
    """
    success_url = settings.GOOGLE_LOGIN_SUCCESS_URL
    error_url = settings.GOOGLE_LOGIN_ERROR_URL

    stored_state = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not stored_state or stored_state != state or not _is_valid_state_token(state):
        return RedirectResponse(url=f"{error_url}?code=invalid_state")

    try:
        token_data = await google_svc.exchange_code(code)
        userinfo = await google_svc.get_userinfo(token_data["access_token"])
    except Exception:
        return RedirectResponse(url=f"{error_url}?code=google_error")

    if not userinfo.get("email_verified", False):
        return RedirectResponse(url=f"{error_url}?code=email_not_verified")

    google_id = userinfo["sub"]
    google_email = userinfo["email"]

    account = await google_svc.get_account_by_google_id(session, google_id)
    if account:
        user = await users_svc.get_user_by_id(session, account.user_id)
        if user is None:
            return RedirectResponse(url=f"{error_url}?code=account_error")
    else:
        user = await users_svc.get_user_by_email(session, google_email)
        if user is None:
            user = await users_svc.create_google_user(
                session, name=userinfo.get("name", google_email), email=google_email
            )
            await session.flush()
        await google_svc.link_account(session, user.id, google_id, google_email)

    if not user.email_verified:
        user.email_verified = True
        session.add(user)

    redirect = RedirectResponse(url=success_url)
    redirect.delete_cookie(_OAUTH_STATE_COOKIE)
    await auth_service.issue_session(session, redirect, user.id)
    return redirect
