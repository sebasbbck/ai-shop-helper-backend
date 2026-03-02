from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core import security
from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.deps import CurrentUser, SessionDep
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.auth import RefreshToken
from ai_shop_helper_backend.schemas.auth import Token
from ai_shop_helper_backend.schemas.users import UserCreate, UserPublic
from ai_shop_helper_backend.services import users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserCreate,
    session: SessionDep,
) -> UserPublic:
    """Register a new user.

    Args:
        user_in (UserCreate): The user data.
        session (AsyncSession): The database session.

    Returns:
        UserPublic: The created user.

    Raises:
        HTTPException: 409 if the email is already registered.
    """
    if await users.get_user_by_email(session, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    return UserPublic.model_validate(await users.create_user(session, user_in))


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> Token:
    """Login a user and return an access token.

    Args:
        response (Response): The HTTP response.
        form_data (OAuth2PasswordRequestForm): The login form data containing username and password.
        session (AsyncSession): The database session.

    Returns:
        Token: The access token.

    Raises:
        HTTPException: 401 if the credentials are invalid.
    """
    user = await users.authenticate(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return await _issue_tokens(session, response, user.id)


@router.post("/refresh", response_model=Token)
async def refresh(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str, Cookie(alias=settings.REFRESH_TOKEN_COOKIE)],
) -> Token:
    """Refresh an access token using a refresh token cookie.

    Args:
        response (Response): The HTTP response.
        session (AsyncSession): The database session.
        refresh_token (str): The refresh token from the cookie.

    Returns:
        Token: The new access token.

    Raises:
        HTTPException: 401 if the refresh token is invalid or expired.
    """
    result = await session.exec(
        select(RefreshToken).where(
            RefreshToken.token == refresh_token,
            RefreshToken.expires_at > get_datetime_utc(),
        )
    )
    token_record = result.first()
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    await session.delete(token_record)
    return await _issue_tokens(session, response, token_record.user_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    current_user: CurrentUser,
    session: SessionDep,
) -> None:
    """Logout the current user by deleting their refresh tokens and clearing the cookie.

    Args:
        response (Response): The HTTP response.
        current_user (User): The current authenticated user.
        session (AsyncSession): The database session.
    """
    await session.exec(
        delete(RefreshToken).where(col(RefreshToken.user_id) == current_user.id)
    )
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE,
        path=settings.refresh_token_path,
        httponly=True,
        secure=True,
        samesite="strict",
    )


async def _issue_tokens(
    session: AsyncSession,
    response: Response,
    user_id: UUID,
) -> Token:
    """Issue a new access token and refresh token.

    Args:
        session (AsyncSession): The database session.
        response (Response): The HTTP response.
        user_id (UUID): The user ID.

    Returns:
        Token: The access token.
    """
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
    return Token(access_token=security.create_access_token(str(user_id)))
