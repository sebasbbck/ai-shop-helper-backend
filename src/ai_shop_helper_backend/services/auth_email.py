import secrets
from datetime import timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.email_types import EmailType
from ai_shop_helper_backend.core.security import hash_password
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.auth import RefreshToken
from ai_shop_helper_backend.models.auth_email import AuthEmailToken
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.services import users as users_service
from ai_shop_helper_backend.services.email import outbox

PURPOSE_VERIFY = "verify_email"
PURPOSE_RESET = "reset_password"


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _is_expired(tok: AuthEmailToken) -> bool:
    """Return True if the token's expiry has passed (tz-safe)."""
    expires_at = tok.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return get_datetime_utc() > expires_at


async def _throttled(session: AsyncSession, user_id: UUID, purpose: str) -> bool:
    """Return True if a resend for (user_id, purpose) should be skipped.

    Skips when the most recent token was created within EMAIL_RESEND_COOLDOWN_S,
    or when the count in the last hour is >= EMAIL_RESEND_MAX_PER_HOUR.
    """
    now = get_datetime_utc()
    one_hour_ago = now - timedelta(seconds=3600)

    result = await session.exec(
        select(AuthEmailToken)
        .where(
            AuthEmailToken.user_id == user_id,
            AuthEmailToken.purpose == purpose,
            AuthEmailToken.created_at >= one_hour_ago,
        )
        .order_by(AuthEmailToken.created_at.desc())
    )
    recent = result.all()

    if len(recent) >= settings.EMAIL_RESEND_MAX_PER_HOUR:
        return True

    if recent:
        latest = recent[0]
        created_at = latest.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        elapsed = (now - created_at).total_seconds()
        if elapsed < settings.EMAIL_RESEND_COOLDOWN_S:
            return True

    return False


async def _issue_and_send(
    session: AsyncSession,
    user: User,
    purpose: str,
    email_type: EmailType,
    locale: str,
) -> None:
    """Create a token row, build the email payload, and enqueue the email."""
    now = get_datetime_utc()
    if purpose == PURPOSE_VERIFY:
        expires_at = now + timedelta(hours=settings.EMAIL_VERIFY_TTL_HOURS)
    else:
        expires_at = now + timedelta(minutes=settings.EMAIL_RESET_TTL_MINUTES)

    token_value = _new_token()
    token = AuthEmailToken(
        user_id=user.id,
        token=token_value,
        purpose=purpose,
        expires_at=expires_at,
    )
    session.add(token)

    if purpose == PURPOSE_VERIFY:
        url = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={token_value}"
        data = {
            "verify_url": url,
            "expiry_hours": settings.EMAIL_VERIFY_TTL_HOURS,
        }
    else:
        url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token_value}"
        data = {
            "reset_url": url,
            "expiry_minutes": settings.EMAIL_RESET_TTL_MINUTES,
        }

    await outbox.enqueue(
        session,
        email_type=email_type,
        to_email=user.email,
        first_name=user.name,
        locale=locale,
        data=data,
        external_id=token_value,
    )


async def start_verification(session: AsyncSession, user: User, locale: str) -> None:
    """Issue and enqueue a verification email for a newly registered user."""
    await _issue_and_send(session, user, PURPOSE_VERIFY, EmailType.VERIFY_EMAIL, locale)


async def resend_verification(session: AsyncSession, email: str, locale: str) -> None:
    """Resend a verification email — enumeration-safe, never raises on missing/verified/throttled."""
    user = await users_service.get_user_by_email(session, email)
    if user is None:
        return
    if user.email_verified:
        return
    if await _throttled(session, user.id, PURPOSE_VERIFY):
        return
    await _issue_and_send(session, user, PURPOSE_VERIFY, EmailType.VERIFY_EMAIL, locale)


async def verify(session: AsyncSession, token_value: str) -> User:
    """Consume a verify token; mark the user as verified.

    Raises HTTPException(400) on missing, already-used, or expired token.
    """
    result = await session.exec(
        select(AuthEmailToken).where(
            AuthEmailToken.token == token_value,
            AuthEmailToken.purpose == PURPOSE_VERIFY,
        )
    )
    tok = result.first()

    if tok is None or tok.used_at is not None or _is_expired(tok):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await users_service.get_user_by_id(session, tok.user_id)
    user.email_verified = True
    tok.used_at = get_datetime_utc()
    session.add(user)
    session.add(tok)
    return user


async def start_password_reset(session: AsyncSession, email: str, locale: str) -> None:
    """Issue and enqueue a password-reset email — enumeration-safe, never raises."""
    user = await users_service.get_user_by_email(session, email)
    if user is None:
        return
    if await _throttled(session, user.id, PURPOSE_RESET):
        return
    await _issue_and_send(session, user, PURPOSE_RESET, EmailType.RESET_PASSWORD, locale)


async def reset_password(
    session: AsyncSession, token_value: str, new_password: str
) -> User:
    """Consume a reset token; update the password and revoke all refresh tokens.

    Raises HTTPException(400) on missing, already-used, or expired token.
    """
    result = await session.exec(
        select(AuthEmailToken).where(
            AuthEmailToken.token == token_value,
            AuthEmailToken.purpose == PURPOSE_RESET,
        )
    )
    tok = result.first()

    if tok is None or tok.used_at is not None or _is_expired(tok):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await users_service.get_user_by_id(session, tok.user_id)
    user.hashed_password = hash_password(new_password)
    tok.used_at = get_datetime_utc()

    await session.exec(delete(RefreshToken).where(RefreshToken.user_id == user.id))

    session.add(user)
    session.add(tok)
    return user
