from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete
from sqlmodel import col, select

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.deps import CurrentUser, SessionDep
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.auth import RefreshToken
from ai_shop_helper_backend.schemas.auth import (
    ForgotPasswordRequest,
    MessageResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    Token,
    VerifyEmailRequest,
)
from ai_shop_helper_backend.schemas.users import UserCreate, UserPublic
from ai_shop_helper_backend.services import auth_email, referrals, users
from ai_shop_helper_backend.services.auth import issue_session

router = APIRouter(prefix="/auth", tags=["auth"])


def _email_locale(request: Request) -> str:
    """Resolve the preferred email locale from request context.

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        str: The resolved locale code ("en" or "es").
    """
    cookie = request.cookies.get("NEXT_LOCALE")
    if cookie in ("en", "es"):
        return cookie
    accept = request.headers.get("accept-language", "").lower()
    if accept.startswith("en"):
        return "en"
    return "es"


@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserCreate,
    request: Request,
    session: SessionDep,
) -> UserPublic:
    """Register a new user.

    Args:
        user_in (UserCreate): The user data.
        request (Request): The incoming HTTP request.
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
    user = await users.create_user(session, user_in)
    await session.flush()
    if user_in.referral_code:
        await referrals.record_signup(session, user_in.referral_code, user.id)
    await auth_email.start_verification(session, user, _email_locale(request))
    return UserPublic.model_validate(user)


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
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="email_not_verified",
        )
    return await issue_session(session, response, user.id)


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
        cleared = Response()
        cleared.delete_cookie(
            key=settings.REFRESH_TOKEN_COOKIE,
            path=settings.refresh_token_path,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"set-cookie": cleared.headers["set-cookie"]},
        )
    await session.delete(token_record)
    return await issue_session(session, response, token_record.user_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
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
    token_value = request.cookies.get(settings.REFRESH_TOKEN_COOKIE)
    if token_value:
        await session.exec(
            delete(RefreshToken).where(col(RefreshToken.token) == token_value)
        )
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE,
        path=settings.refresh_token_path,
        httponly=True,
        secure=True,
        samesite="strict",
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    body: VerifyEmailRequest,
    session: SessionDep,
) -> MessageResponse:
    """Verify a user's email address using a token.

    Args:
        body (VerifyEmailRequest): The verification token.
        session (AsyncSession): The database session.

    Returns:
        MessageResponse: Confirmation message.

    Raises:
        HTTPException: 400 if the token is invalid or expired.
    """
    await auth_email.verify(session, body.token)
    return MessageResponse(message="Email verified")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    session: SessionDep,
) -> MessageResponse:
    """Resend a verification email — enumeration-safe, always returns the same response.

    Args:
        body (ResendVerificationRequest): The email address to resend to.
        request (Request): The incoming HTTP request.
        session (AsyncSession): The database session.

    Returns:
        MessageResponse: Generic confirmation that does not reveal account existence.
    """
    await auth_email.resend_verification(session, body.email, _email_locale(request))
    return MessageResponse(
        message="If an account exists and is unverified, a verification email has been sent"
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: SessionDep,
) -> MessageResponse:
    """Request a password reset email — enumeration-safe, always returns the same response.

    Args:
        body (ForgotPasswordRequest): The email address to send the reset link to.
        request (Request): The incoming HTTP request.
        session (AsyncSession): The database session.

    Returns:
        MessageResponse: Generic confirmation that does not reveal account existence.
    """
    await auth_email.start_password_reset(session, body.email, _email_locale(request))
    return MessageResponse(
        message="If an account exists, a password reset email has been sent"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    session: SessionDep,
) -> MessageResponse:
    """Reset a user's password using a token.

    Args:
        body (ResetPasswordRequest): The reset token and new password.
        session (AsyncSession): The database session.

    Returns:
        MessageResponse: Confirmation message.

    Raises:
        HTTPException: 400 if the token is invalid or expired.
    """
    await auth_email.reset_password(session, body.token, body.new_password)
    return MessageResponse(message="Password updated")
