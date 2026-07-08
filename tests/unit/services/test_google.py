"""Unit tests for services/google.py — DB and HTTP calls mocked."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_shop_helper_backend.models.google_credentials import GoogleCredential
from ai_shop_helper_backend.services.google import (
    build_auth_url,
    delete_credentials,
    exchange_code,
    get_credentials,
    get_credentials_by_google_id,
    get_userinfo,
    get_valid_access_token,
    google_get,
    google_post,
    revoke_google_token,
    upsert_credentials,
)


class TestGetCredentials:
    async def test_returns_credential_when_found(self, mock_session: AsyncMock) -> None:
        cred = MagicMock(spec=GoogleCredential)
        mock_session.exec.return_value.first.return_value = cred

        result = await get_credentials(mock_session, uuid.uuid4())

        mock_session.exec.assert_called_once()
        assert result is cred

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_credentials(mock_session, uuid.uuid4())

        assert result is None


class TestGetCredentialsByGoogleId:
    async def test_returns_credential_when_found(self, mock_session: AsyncMock) -> None:
        cred = MagicMock(spec=GoogleCredential)
        mock_session.exec.return_value.first.return_value = cred

        result = await get_credentials_by_google_id(mock_session, "google-sub-123")

        mock_session.exec.assert_called_once()
        assert result is cred

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_credentials_by_google_id(mock_session, "nonexistent-sub")

        assert result is None


class TestRevokeGoogleToken:
    async def test_posts_to_revoke_url(self) -> None:
        mock_post = AsyncMock(return_value=MagicMock())

        with patch(
            "ai_shop_helper_backend.services.google.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post
            await revoke_google_token("some-refresh-token")

        call_args = mock_post.call_args
        assert "https://oauth2.googleapis.com/revoke" in call_args[0]
        assert call_args[1]["params"]["token"] == "some-refresh-token"

    async def test_does_not_raise_on_network_error(self) -> None:
        with patch(
            "ai_shop_helper_backend.services.google.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Network error")
            )
            await revoke_google_token("any-token")


class TestUpsertCredentials:
    async def test_creates_new_credential_when_none_exists(
        self, mock_session: AsyncMock
    ) -> None:
        mock_session.exec.return_value.first.return_value = None
        user_id = uuid.uuid4()

        result = await upsert_credentials(
            session=mock_session,
            user_id=user_id,
            google_id="gid-123",
            google_email="user@example.com",
            access_token="access-tok",
            refresh_token="refresh-tok",
            expires_in=3600,
            scopes="openid email",
        )

        mock_session.add.assert_called_once()
        assert result.user_id == user_id
        assert result.google_id == "gid-123"

    async def test_updates_existing_credential(self, mock_session: AsyncMock) -> None:
        existing = MagicMock(spec=GoogleCredential)
        mock_session.exec.return_value.first.return_value = existing

        result = await upsert_credentials(
            session=mock_session,
            user_id=uuid.uuid4(),
            google_id="gid-new",
            google_email="new@example.com",
            access_token="new-access",
            refresh_token="new-refresh",
            expires_in=3600,
            scopes="openid email profile",
        )

        mock_session.add.assert_called_once_with(existing)
        assert result is existing
        assert existing.access_token == "new-access"


class TestDeleteCredentials:
    async def test_calls_session_delete(self, mock_session: AsyncMock) -> None:
        cred = MagicMock(spec=GoogleCredential)

        await delete_credentials(mock_session, cred)

        mock_session.delete.assert_called_once_with(cred)


class TestGetValidAccessToken:
    async def test_raises_when_no_credentials(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Google account not connected"):
            await get_valid_access_token(mock_session, uuid.uuid4())

    async def test_returns_token_when_valid(self, mock_session: AsyncMock) -> None:
        cred = MagicMock(spec=GoogleCredential)
        cred.access_token = "valid-token"
        cred.token_expires_at = datetime(2099, 1, 1, tzinfo=UTC)
        mock_session.exec.return_value.first.return_value = cred

        result = await get_valid_access_token(mock_session, uuid.uuid4())

        assert result == "valid-token"

    async def test_refreshes_when_token_expired(self, mock_session: AsyncMock) -> None:
        cred = MagicMock(spec=GoogleCredential)
        cred.access_token = "old-token"
        cred.token_expires_at = datetime(2000, 1, 1, tzinfo=UTC)
        cred.refresh_token = "refresh-tok"
        mock_session.exec.return_value.first.return_value = cred

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_post = AsyncMock(return_value=mock_response)

        with patch(
            "ai_shop_helper_backend.services.google.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post
            result = await get_valid_access_token(mock_session, uuid.uuid4())

        assert result == "new-token"

    async def test_refreshes_and_updates_refresh_token_when_provided(
        self, mock_session: AsyncMock
    ) -> None:
        cred = MagicMock(spec=GoogleCredential)
        cred.access_token = "old-token"
        cred.token_expires_at = datetime(2000, 1, 1, tzinfo=UTC)
        cred.refresh_token = "old-refresh"
        mock_session.exec.return_value.first.return_value = cred

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
            "refresh_token": "new-refresh-token",
        }
        mock_post = AsyncMock(return_value=mock_response)

        with patch(
            "ai_shop_helper_backend.services.google.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post
            result = await get_valid_access_token(mock_session, uuid.uuid4())

        assert result == "new-token"
        assert cred.refresh_token == "new-refresh-token"


class TestBuildAuthUrl:
    def test_contains_client_id_and_state(self) -> None:
        url = build_auth_url("test-state-123")
        assert "state=test-state-123" in url
        assert "https://accounts.google.com/o/oauth2/v2/auth" in url

    def test_uses_login_scopes_when_provided(self) -> None:
        from ai_shop_helper_backend.services.google import LOGIN_SCOPES

        url = build_auth_url("state", scopes=LOGIN_SCOPES)
        assert "openid" in url


class TestExchangeCode:
    async def test_posts_to_token_endpoint_and_returns_json(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "tok",
            "refresh_token": "ref",
        }
        mock_post = AsyncMock(return_value=mock_response)

        with patch(
            "ai_shop_helper_backend.services.google.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post
            result = await exchange_code("auth-code")

        assert result["access_token"] == "tok"
        call_args = mock_post.call_args
        assert "https://oauth2.googleapis.com/token" in call_args[0]
        assert call_args[1]["data"]["code"] == "auth-code"


class TestGetUserinfo:
    async def test_gets_userinfo_with_bearer_token(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"sub": "123", "email": "u@example.com"}
        mock_get = AsyncMock(return_value=mock_response)

        with patch(
            "ai_shop_helper_backend.services.google.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.get = mock_get
            result = await get_userinfo("access-token")

        assert result["sub"] == "123"
        call_args = mock_get.call_args
        assert "Bearer access-token" in call_args[1]["headers"]["Authorization"]


class TestGoogleGet:
    async def test_calls_url_with_params_and_auth(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "value"}
        mock_get = AsyncMock(return_value=mock_response)

        with patch(
            "ai_shop_helper_backend.services.google.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.get = mock_get
            result = await google_get(
                "my-token", "https://api.example.com", {"key": "val"}
            )

        assert result["data"] == "value"
        call_args = mock_get.call_args
        assert call_args[1]["params"] == {"key": "val"}
        assert "Bearer my-token" in call_args[1]["headers"]["Authorization"]


class TestGooglePost:
    async def test_posts_json_payload_with_auth(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "ok"}
        mock_post = AsyncMock(return_value=mock_response)

        with patch(
            "ai_shop_helper_backend.services.google.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post
            result = await google_post(
                "my-token", "https://api.example.com", {"q": "query"}
            )

        assert result["result"] == "ok"
        call_args = mock_post.call_args
        assert call_args[1]["json"] == {"q": "query"}
        assert "Bearer my-token" in call_args[1]["headers"]["Authorization"]
