import json
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("cryptography")

from ai_shop_helper_backend.connections import google as google_conn
from ai_shop_helper_backend.connections.google import GoogleConnectionProvider
from ai_shop_helper_backend.connections.registry import get_connection_provider
from ai_shop_helper_backend.core.crypto import encrypt
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.connections import Connection, ConnectionType


def _make_connection(secrets: dict) -> Connection:
    return Connection(
        project_id=uuid.uuid4(),
        connection_type=ConnectionType.google,
        secrets_encrypted=encrypt(json.dumps(secrets)),
    )


class TestBuildSecrets:
    def test_builds_expected_fields(self) -> None:
        secrets = google_conn.build_secrets(
            access_token="at",
            refresh_token="rt",
            expires_in=3600,
            scopes="openid email",
            google_email="me@example.com",
        )

        assert secrets["access_token"] == "at"
        assert secrets["refresh_token"] == "rt"
        assert secrets["scopes"] == "openid email"
        assert secrets["google_email"] == "me@example.com"
        assert "token_expires_at" in secrets


class TestGoogleConnectionProvider:
    async def test_get_injected_inputs_returns_access_token(self) -> None:
        connection = _make_connection(
            {"access_token": "live-token", "refresh_token": "rt"}
        )
        provider = GoogleConnectionProvider()

        result = await provider.get_injected_inputs(connection)

        assert result == {"access_token": "live-token"}


class TestGetValidAccessToken:
    async def test_returns_stored_token_when_not_expired(
        self, mock_session: AsyncMock
    ) -> None:
        secrets = google_conn.build_secrets(
            access_token="fresh-token",
            refresh_token="rt",
            expires_in=3600,
            scopes="",
            google_email="me@example.com",
        )
        connection = _make_connection(secrets)
        with patch(
            "ai_shop_helper_backend.connections.google.get_connection_by_project",
            new_callable=AsyncMock,
            return_value=connection,
        ):
            token = await google_conn.get_valid_access_token(
                mock_session, connection.project_id
            )

        assert token == "fresh-token"
        mock_session.add.assert_not_called()

    async def test_refreshes_when_expired(self, mock_session: AsyncMock) -> None:
        secrets = {
            "access_token": "stale-token",
            "refresh_token": "rt",
            "token_expires_at": (get_datetime_utc() - timedelta(hours=1)).isoformat(),
            "scopes": "",
            "google_email": "me@example.com",
        }
        connection = _make_connection(secrets)

        refresh_response = AsyncMock()
        refresh_response.json = lambda: {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        refresh_response.raise_for_status = lambda: None

        with (
            patch(
                "ai_shop_helper_backend.connections.google.get_connection_by_project",
                new_callable=AsyncMock,
                return_value=connection,
            ),
            patch("httpx.AsyncClient.post", return_value=refresh_response),
        ):
            token = await google_conn.get_valid_access_token(
                mock_session, connection.project_id
            )

        assert token == "new-token"
        mock_session.add.assert_called_once_with(connection)

    async def test_raises_when_no_connection(self, mock_session: AsyncMock) -> None:
        with patch(
            "ai_shop_helper_backend.connections.google.get_connection_by_project",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with pytest.raises(ValueError, match="not connected"):
                await google_conn.get_valid_access_token(mock_session, uuid.uuid4())


class TestConnectionRegistry:
    def test_get_connection_provider_returns_google_provider(self) -> None:
        provider = get_connection_provider(ConnectionType.google)
        assert isinstance(provider, GoogleConnectionProvider)
