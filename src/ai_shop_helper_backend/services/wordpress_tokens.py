import secrets
from datetime import UTC, timedelta
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.wordpress_tokens import WordpressToken

TOKEN_TTL_MINUTES = 15


async def create_token(session: AsyncSession, project_id: UUID) -> WordpressToken:
    """Create a new short-lived handshake token for a WordPress connection attempt.

    Args:
        session (AsyncSession): The database session.
        project_id (UUID): The project ID this token is associated with.

    Returns:
        WordpressToken: The created (not yet committed) token row.
    """
    expires_at = get_datetime_utc() + timedelta(minutes=TOKEN_TTL_MINUTES)
    token = WordpressToken(
        token=secrets.token_hex(32),
        project_id=project_id,
        expires_at=expires_at,
    )
    session.add(token)
    return token


async def get_token(session: AsyncSession, token_value: str) -> WordpressToken | None:
    """Retrieve a handshake token by its value.

    Args:
        session (AsyncSession): The database session.
        token_value (str): The raw token string.

    Returns:
        WordpressToken | None: The token row if found.
    """
    result = await session.exec(
        select(WordpressToken).where(WordpressToken.token == token_value)
    )
    return result.first()


def is_expired(token: WordpressToken) -> bool:
    """Check whether a handshake token has passed its expiry time.

    Args:
        token (WordpressToken): The token to check.

    Returns:
        bool: True if the token is expired.
    """
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return get_datetime_utc() > expires_at


async def delete_token(session: AsyncSession, token: WordpressToken) -> None:
    """Delete a handshake token (invalidation after use or expiry).

    Args:
        session (AsyncSession): The database session.
        token (WordpressToken): The token to delete.
    """
    await session.delete(token)
