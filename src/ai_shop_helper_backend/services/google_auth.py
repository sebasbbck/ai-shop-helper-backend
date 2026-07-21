import urllib.parse
from uuid import UUID

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.models.google_account import GoogleAccount

LOGIN_SCOPES = "openid email profile"


async def get_account_by_google_id(
    session: AsyncSession, google_id: str
) -> GoogleAccount | None:
    """Get the identity link for a Google account, if one exists.

    Args:
        session (AsyncSession): The database session.
        google_id (str): The Google account's subject id.

    Returns:
        GoogleAccount | None: The identity link if found, None otherwise.
    """
    result = await session.exec(
        select(GoogleAccount).where(GoogleAccount.google_id == google_id)
    )
    return result.first()


async def link_account(
    session: AsyncSession, user_id: UUID, google_id: str, google_email: str
) -> GoogleAccount:
    """Link a Google identity to a user for login.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user to link.
        google_id (str): The Google account's subject id.
        google_email (str): The Google account's email.

    Returns:
        GoogleAccount: The created identity link.
    """
    account = GoogleAccount(
        user_id=user_id, google_id=google_id, google_email=google_email
    )
    session.add(account)
    return account


def build_auth_url(state: str) -> str:
    """Build the Google OAuth URL for login (identity scopes only).

    Args:
        state (str): The CSRF state token to round-trip through Google.

    Returns:
        str: The Google OAuth authorization URL.
    """
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "response_type": "code",
        "scope": LOGIN_SCOPES,
        "redirect_uri": settings.GOOGLE_LOGIN_REDIRECT_URI,
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        params
    )


async def exchange_code(code: str) -> dict:
    """Exchange an authorization code for a Google access token.

    Args:
        code (str): The authorization code from the callback.

    Returns:
        dict: The token response from Google.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_LOGIN_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


async def get_userinfo(access_token: str) -> dict:
    """Fetch the Google user's profile info.

    Args:
        access_token (str): A valid Google access token.

    Returns:
        dict: The userinfo response from Google.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
