import secrets
from datetime import datetime, timedelta

import jwt
from pwdlib import PasswordHash

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.utils import get_datetime_utc

pwd_hash = PasswordHash.recommended()


def hash_password(plain: str) -> str:
    """Hash a plain password.

    Args:
        plain (str): The plain password to hash.

    Returns:
        str: The hashed password.
    """
    return pwd_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain (str): The plain password to verify.
        hashed (str): The hashed password to verify against.

    Returns:
        bool: True if the password is correct, False otherwise.
    """
    return pwd_hash.verify(plain, hashed)


def create_access_token(subject: str, is_superuser: bool) -> str:
    """Create a JWT access token.

    Args:
        subject (str): The subject (i.e., user ID) to include in the token payload.
        is_superuser (bool): Whether the user is a superuser.

    Returns:
        str: The generated JWT access token.
    """
    now = get_datetime_utc()
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": subject, "iat": now, "exp": expire, "is_superuser": is_superuser},
        settings.SECRET_KEY,
        algorithm=settings.KEY_ALGORITHM,
    )


def decode_access_token(token: str) -> str | None:
    """Decode a JWT access token and return the subject (i.e., user ID).

    Args:
        token (str): The JWT access token to decode.

    Returns:
        str | None: The subject if the token is valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.KEY_ALGORITHM]
        )
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def generate_refresh_token() -> str:
    """Generate a secure random refresh token.

    Returns:
        str: The generated refresh token.
    """
    return secrets.token_urlsafe(32)


def refresh_token_expiry() -> datetime:
    """Calculate the expiration datetime for a refresh token.

    Returns:
        datetime: The expiration datetime for the refresh token.
    """
    return get_datetime_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
