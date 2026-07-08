import urllib.parse
from datetime import datetime, timedelta
from uuid import UUID

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.google_credentials import GoogleCredential

LOGIN_SCOPES = "openid email profile"

FULL_SCOPES = (
    "openid email profile "
    "https://www.googleapis.com/auth/userinfo.profile "
    "https://www.googleapis.com/auth/userinfo.email "
    "https://www.googleapis.com/auth/webmasters.readonly "
    "https://www.googleapis.com/auth/analytics.readonly"
)

_TOKEN_REFRESH_BUFFER_SECONDS = 60


async def get_credentials(
    session: AsyncSession, user_id: UUID
) -> GoogleCredential | None:
    result = await session.exec(
        select(GoogleCredential).where(GoogleCredential.user_id == user_id)
    )
    return result.first()


async def get_credentials_by_google_id(
    session: AsyncSession, google_id: str
) -> GoogleCredential | None:
    result = await session.exec(
        select(GoogleCredential).where(GoogleCredential.google_id == google_id)
    )
    return result.first()


async def revoke_google_token(token: str) -> None:
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except Exception:
            pass


async def upsert_credentials(
    session: AsyncSession,
    user_id: UUID,
    google_id: str,
    google_email: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    scopes: str,
) -> GoogleCredential:
    expires_at = _expires_at(expires_in)
    existing = await get_credentials(session, user_id)
    if existing:
        existing.google_id = google_id
        existing.google_email = google_email
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.token_expires_at = expires_at
        existing.scopes = scopes
        session.add(existing)
        return existing

    credential = GoogleCredential(
        user_id=user_id,
        google_id=google_id,
        google_email=google_email,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=expires_at,
        scopes=scopes,
    )
    session.add(credential)
    return credential


async def delete_credentials(
    session: AsyncSession, credential: GoogleCredential
) -> None:
    await session.delete(credential)


def _expires_at(seconds: int) -> datetime:
    return get_datetime_utc() + timedelta(
        seconds=seconds - _TOKEN_REFRESH_BUFFER_SECONDS
    )


async def _refresh_access_token(
    credential: GoogleCredential, session: AsyncSession
) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": credential.refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        token_data = response.json()

    credential.access_token = token_data["access_token"]
    credential.token_expires_at = _expires_at(int(token_data.get("expires_in", 3600)))
    if token_data.get("refresh_token"):
        credential.refresh_token = token_data["refresh_token"]
    session.add(credential)
    return credential.access_token


async def get_valid_access_token(session: AsyncSession, user_id: UUID) -> str:
    credential = await get_credentials(session, user_id)
    if not credential:
        raise ValueError("Google account not connected")

    if credential.token_expires_at <= get_datetime_utc():
        return await _refresh_access_token(credential, session)

    return credential.access_token


def build_auth_url(state: str, scopes: str = FULL_SCOPES) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "response_type": "code",
        "scope": scopes,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "state": state,
        "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        params
    )


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


async def get_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def google_get(access_token: str, url: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def google_post(access_token: str, url: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
