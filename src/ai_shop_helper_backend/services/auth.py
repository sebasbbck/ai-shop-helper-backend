from uuid import UUID

from fastapi import HTTPException, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core import security
from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.models.auth import RefreshToken
from ai_shop_helper_backend.schemas.auth import Token
from ai_shop_helper_backend.services import users


async def issue_session(
    session: AsyncSession,
    response: Response,
    user_id: UUID,
) -> Token:
    """Start an app session for a user.

    Creates and persists a refresh token, sets it as an httpOnly cookie on the
    response, and returns an access token. Shared by every auth entry point
    (password login, token refresh, social login).

    Args:
        session (AsyncSession): The database session.
        response (Response): The HTTP response the refresh cookie is set on.
        user_id (UUID): The user to start a session for.

    Returns:
        Token: The access token.

    Raises:
        HTTPException: 401 if the user does not exist.
    """
    user = await users.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    refresh_token_value = security.generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token=refresh_token_value,
            expires_at=security.refresh_token_expiry(),
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
        access_token=security.create_access_token(str(user_id), user.is_superuser)
    )
