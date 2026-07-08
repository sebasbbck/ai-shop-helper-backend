"""Unit tests for services/google.py — DB and HTTP calls mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

from ai_shop_helper_backend.models.google_credentials import GoogleCredential
from ai_shop_helper_backend.services.google import (
    get_credentials_by_google_id,
    revoke_google_token,
)


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
