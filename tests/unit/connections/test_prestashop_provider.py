import base64
import json
import uuid
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("cryptography")

from ai_shop_helper_backend.connections.prestashop import PrestashopProvider
from ai_shop_helper_backend.connections.registry import get_connection_provider
from ai_shop_helper_backend.core.crypto import encrypt
from ai_shop_helper_backend.models.connections import Connection, ConnectionType


def _make_connection(shop_url: str, api_url: str, ws_key: str) -> Connection:
    secrets = {"shop_url": shop_url, "api_url": api_url, "ws_key": ws_key}
    return Connection(
        project_id=uuid.uuid4(),
        connection_type=ConnectionType.prestashop,
        secrets_encrypted=encrypt(json.dumps(secrets)),
    )


class TestPrestashopProvider:
    async def test_get_injected_inputs_returns_api_url(self) -> None:
        connection = _make_connection(
            shop_url="https://shop.test",
            api_url="https://shop.test/api",
            ws_key="ABCDEF0123456789ABCDEF0123456789",
        )
        provider = PrestashopProvider()
        credentials = await provider.get_credentials(AsyncMock(), connection)
        result = provider.to_injected_inputs(credentials)

        assert result["url"] == "https://shop.test/api"

    async def test_get_injected_inputs_builds_auth_token_key_as_user_empty_password(
        self,
    ) -> None:
        connection = _make_connection(
            shop_url="https://shop.test",
            api_url="https://shop.test/api",
            ws_key="WSKEY123",
        )
        provider = PrestashopProvider()
        credentials = await provider.get_credentials(AsyncMock(), connection)
        result = provider.to_injected_inputs(credentials)

        expected = base64.b64encode(b"WSKEY123:").decode()
        assert result["auth_token"] == expected
        raw = base64.b64decode(result["auth_token"]).decode()
        assert raw == "WSKEY123:"

    async def test_get_injected_inputs_keys_are_url_and_auth_token(self) -> None:
        connection = _make_connection(
            shop_url="https://shop.test",
            api_url="https://shop.test/api",
            ws_key="k",
        )
        provider = PrestashopProvider()
        credentials = await provider.get_credentials(AsyncMock(), connection)
        result = provider.to_injected_inputs(credentials)

        assert set(result.keys()) == {"url", "auth_token"}


class TestPrestashopRegistry:
    def test_get_connection_provider_returns_prestashop_provider(self) -> None:
        provider = get_connection_provider(ConnectionType.prestashop)
        assert isinstance(provider, PrestashopProvider)
