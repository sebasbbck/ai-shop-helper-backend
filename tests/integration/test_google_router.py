"""Integration tests for the Google OAuth2 router."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.security import hash_password
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.google_credentials import GoogleCredential
from ai_shop_helper_backend.models.users import User


def _state_token(mode: str, user_id: object = None) -> str:
    now = get_datetime_utc()
    payload: dict = {
        "mode": mode,
        "nonce": "testnonce",
        "exp": now + timedelta(minutes=10),
    }
    if user_id is not None:
        payload["user_id"] = str(user_id)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.KEY_ALGORITHM)


def _google_token_data(
    google_id: str = "google-sub-001",
    email: str = "user@gmail.com",
    name: str = "Test User",
) -> tuple[dict, dict]:
    token_data = {
        "access_token": "goog-access-token",
        "refresh_token": "goog-refresh-token",
        "expires_in": 3600,
        "scope": "openid email",
    }
    userinfo = {"sub": google_id, "email": email, "name": name, "email_verified": True}
    return token_data, userinfo


async def _add_google_credential(
    session: AsyncSession, user_id: object, google_id: str = "test-sub"
) -> GoogleCredential:
    cred = GoogleCredential(
        user_id=user_id,
        google_id=google_id,
        google_email="user@gmail.com",
        access_token="access-token",
        refresh_token="refresh-token",
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes="openid email",
    )
    session.add(cred)
    await session.commit()
    return cred


class TestGoogleLogin:
    async def test_returns_auth_url_without_authentication(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/google/login")

        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "accounts.google.com" in data["auth_url"]

    async def test_login_auth_url_uses_minimal_scopes(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/google/login")

        auth_url = response.json()["auth_url"]
        assert "analytics" not in auth_url
        assert "webmasters" not in auth_url


class TestGoogleDisconnect:
    async def test_returns_404_when_not_connected(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        response = await client.delete("/google/disconnect", headers=auth_headers)

        assert response.status_code == 404

    async def test_revokes_token_and_returns_204(
        self, client: AsyncClient, auth_headers: dict, session: AsyncSession
    ) -> None:
        me = await client.get("/users/me", headers=auth_headers)
        user_id = me.json()["id"]
        await _add_google_credential(session, user_id)

        with patch(
            "ai_shop_helper_backend.services.google.revoke_google_token",
            new_callable=AsyncMock,
        ) as mock_revoke:
            response = await client.delete("/google/disconnect", headers=auth_headers)

        assert response.status_code == 204
        mock_revoke.assert_awaited_once_with("refresh-token")

        result = await session.exec(
            select(GoogleCredential).where(GoogleCredential.user_id == user_id)
        )
        assert result.first() is None


class TestGoogleCallbackConnect:
    async def test_conflict_when_google_id_linked_to_another_user(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        user1 = User(
            email="user1@example.com",
            name="User 1",
            hashed_password=hash_password("pass"),
        )
        user2 = User(
            email="user2@example.com",
            name="User 2",
            hashed_password=hash_password("pass"),
        )
        session.add(user1)
        session.add(user2)
        await session.flush()

        await _add_google_credential(session, user1.id, google_id="shared-google-sub")

        token_data, userinfo = _google_token_data(
            google_id="shared-google-sub", email="shared@gmail.com"
        )
        state = _state_token(mode="connect", user_id=user2.id)

        with (
            patch(
                "ai_shop_helper_backend.services.google.exchange_code",
                new_callable=AsyncMock,
                return_value=token_data,
            ),
            patch(
                "ai_shop_helper_backend.services.google.get_userinfo",
                new_callable=AsyncMock,
                return_value=userinfo,
            ),
        ):
            response = await client.get(
                f"/google/callback?code=authcode&state={state}",
                cookies={"oauth_state": state},
            )

        assert response.status_code == 409
        assert "already linked" in response.json()["detail"]


class TestGoogleCallbackLogin:
    async def test_creates_new_user_on_first_google_login(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        token_data, userinfo = _google_token_data(
            google_id="new-user-sub", email="newuser@gmail.com", name="New Google User"
        )
        state = _state_token(mode="login")

        with (
            patch(
                "ai_shop_helper_backend.services.google.exchange_code",
                new_callable=AsyncMock,
                return_value=token_data,
            ),
            patch(
                "ai_shop_helper_backend.services.google.get_userinfo",
                new_callable=AsyncMock,
                return_value=userinfo,
            ),
        ):
            response = await client.get(
                f"/google/callback?code=authcode&state={state}",
                cookies={"oauth_state": state},
            )

        assert response.status_code == 200
        assert "access_token" in response.json()

        result = await session.exec(
            select(User).where(User.email == "newuser@gmail.com")
        )
        user = result.first()
        assert user is not None
        assert user.name == "New Google User"

    async def test_returns_token_for_existing_google_user(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        user = User(
            email="existing@gmail.com",
            name="Existing",
            hashed_password=hash_password("pass"),
        )
        session.add(user)
        await session.flush()
        await _add_google_credential(session, user.id, google_id="existing-sub")

        token_data, userinfo = _google_token_data(
            google_id="existing-sub", email="existing@gmail.com"
        )
        state = _state_token(mode="login")

        with (
            patch(
                "ai_shop_helper_backend.services.google.exchange_code",
                new_callable=AsyncMock,
                return_value=token_data,
            ),
            patch(
                "ai_shop_helper_backend.services.google.get_userinfo",
                new_callable=AsyncMock,
                return_value=userinfo,
            ),
        ):
            response = await client.get(
                f"/google/callback?code=authcode&state={state}",
                cookies={"oauth_state": state},
            )

        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_rejects_unverified_email(self, client: AsyncClient) -> None:
        token_data, userinfo = _google_token_data(
            google_id="unverified-sub", email="unverified@gmail.com"
        )
        userinfo["email_verified"] = False
        state = _state_token(mode="login")

        with (
            patch(
                "ai_shop_helper_backend.services.google.exchange_code",
                new_callable=AsyncMock,
                return_value=token_data,
            ),
            patch(
                "ai_shop_helper_backend.services.google.get_userinfo",
                new_callable=AsyncMock,
                return_value=userinfo,
            ),
        ):
            response = await client.get(
                f"/google/callback?code=authcode&state={state}",
                cookies={"oauth_state": state},
            )

        assert response.status_code == 400
        assert "not verified" in response.json()["detail"]
