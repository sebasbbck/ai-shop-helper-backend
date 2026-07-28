import base64
import json
import uuid
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("cryptography")

from ai_shop_helper_backend.connections.registry import get_connection_provider
from ai_shop_helper_backend.connections.wordpress import WordpressProvider
from ai_shop_helper_backend.core.crypto import encrypt
from ai_shop_helper_backend.models.connections import Connection, ConnectionType


def _make_connection(site_url: str, username: str, app_password: str) -> Connection:
    secrets = {"site_url": site_url, "username": username, "app_password": app_password}
    return Connection(
        project_id=uuid.uuid4(),
        connection_type=ConnectionType.wordpress,
        secrets_encrypted=encrypt(json.dumps(secrets)),
    )


class TestWordpressProvider:
    async def test_get_injected_inputs_returns_url(self) -> None:
        connection = _make_connection(
            site_url="https://example.com",
            username="admin",
            app_password="abc XYZ 123",
        )
        provider = WordpressProvider()
        credentials = await provider.get_credentials(AsyncMock(), connection)
        result = provider.to_injected_inputs(credentials)

        assert result["url"] == "https://example.com"

    async def test_get_injected_inputs_builds_auth_token(self) -> None:
        connection = _make_connection(
            site_url="https://example.com",
            username="admin",
            app_password="abc XYZ 123",
        )
        provider = WordpressProvider()
        credentials = await provider.get_credentials(AsyncMock(), connection)
        result = provider.to_injected_inputs(credentials)

        expected = base64.b64encode(b"admin:abc XYZ 123").decode()
        assert result["auth_token"] == expected

    async def test_get_injected_inputs_keys_are_url_and_auth_token(self) -> None:
        connection = _make_connection(
            site_url="https://shop.test",
            username="user",
            app_password="pw",
        )
        provider = WordpressProvider()
        credentials = await provider.get_credentials(AsyncMock(), connection)
        result = provider.to_injected_inputs(credentials)

        assert set(result.keys()) == {"url", "auth_token"}

    async def test_get_injected_inputs_special_chars_in_password(self) -> None:
        connection = _make_connection(
            site_url="https://shop.test",
            username="editor",
            app_password="p@ss word! 2026",
        )
        provider = WordpressProvider()
        credentials = await provider.get_credentials(AsyncMock(), connection)
        result = provider.to_injected_inputs(credentials)

        raw = base64.b64decode(result["auth_token"]).decode()
        assert raw == "editor:p@ss word! 2026"


class TestConnectionRegistry:
    def test_get_connection_provider_returns_wordpress_provider(self) -> None:
        provider = get_connection_provider(ConnectionType.wordpress)
        assert isinstance(provider, WordpressProvider)

    def test_get_connection_provider_raises_for_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="No connection provider registered"):
            get_connection_provider("prestashop")  # type: ignore[arg-type]
