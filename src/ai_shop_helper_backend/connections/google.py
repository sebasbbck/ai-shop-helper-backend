import json
import urllib.parse
from datetime import datetime, timedelta
from uuid import UUID

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.connections.base import decode_secrets
from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.crypto import encrypt
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.connections import Connection
from ai_shop_helper_backend.services.connections import get_connection_by_project

FULL_SCOPES = (
    "openid email profile "
    "https://www.googleapis.com/auth/webmasters.readonly "
    "https://www.googleapis.com/auth/analytics.readonly"
)

_TOKEN_REFRESH_BUFFER_SECONDS = 60


def build_auth_url(state: str) -> str:
    """Build the Google OAuth URL to connect a project's GA4/Search Console access."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "response_type": "code",
        "scope": FULL_SCOPES,
        "redirect_uri": settings.GOOGLE_CONNECTION_REDIRECT_URI,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "state": state,
        "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        params
    )


async def exchange_code(code: str) -> dict:
    """Exchange an authorization code for Google access + refresh tokens."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_CONNECTION_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


async def get_userinfo(access_token: str) -> dict:
    """Fetch the Google account's profile info (used to show which account is connected)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


def build_secrets(
    access_token: str,
    refresh_token: str,
    expires_in: int,
    scopes: str,
    google_email: str,
) -> dict:
    """Build the secrets dict stored (encrypted) on the project's Connection row."""
    expires_at = get_datetime_utc() + timedelta(
        seconds=expires_in - _TOKEN_REFRESH_BUFFER_SECONDS
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expires_at": expires_at.isoformat(),
        "scopes": scopes,
        "google_email": google_email,
    }


async def _refresh_access_token(secrets: dict) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": secrets["refresh_token"],
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        token_data = response.json()

    expires_at = get_datetime_utc() + timedelta(
        seconds=int(token_data.get("expires_in", 3600)) - _TOKEN_REFRESH_BUFFER_SECONDS
    )
    secrets["access_token"] = token_data["access_token"]
    secrets["token_expires_at"] = expires_at.isoformat()
    if token_data.get("refresh_token"):
        secrets["refresh_token"] = token_data["refresh_token"]
    return secrets


async def get_valid_access_token(session: AsyncSession, project_id: UUID) -> str:
    """Return a valid Google access token for the project's connection, refreshing if needed.

    Args:
        session (AsyncSession): The database session.
        project_id (UUID): The project ID.

    Returns:
        str: A valid Google access token.

    Raises:
        ValueError: If the project has no Google connection.
    """
    connection = await get_connection_by_project(session, project_id)
    if not connection:
        raise ValueError("Google account not connected")

    secrets = decode_secrets(connection)
    expires_at = datetime.fromisoformat(secrets["token_expires_at"])
    if expires_at <= get_datetime_utc():
        secrets = await _refresh_access_token(secrets)
        connection.secrets_encrypted = encrypt(json.dumps(secrets))
        session.add(connection)

    return secrets["access_token"]


async def google_get(access_token: str, url: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            url, params=params, headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        return response.json()


async def google_post(access_token: str, url: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url, json=payload, headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        return response.json()


class GoogleConnectionProvider:
    """Implements ConnectionProvider — exposes a Google access token for agent-run injection."""

    async def get_injected_inputs(self, connection: Connection) -> dict[str, str]:
        secrets = decode_secrets(connection)
        return {"access_token": secrets["access_token"]}
