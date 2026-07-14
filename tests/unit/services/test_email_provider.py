"""Unit tests for services/email/provider.py — httpx transport mocked via MockTransport."""

import json
from typing import Any

import httpx
import pytest

from ai_shop_helper_backend.core.email_types import EmailType, notifuse_language
from ai_shop_helper_backend.services.email.provider import (
    EmailDeliveryError,
    NotifuseProvider,
)

BASE_URL = "https://notifuse.example.com"
API_KEY = "test-api-key"
WORKSPACE_ID = "ws-test-001"


def _make_provider(handler: Any) -> NotifuseProvider:
    return NotifuseProvider(transport=httpx.MockTransport(handler))


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"status": "ok"})


def _error_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(400, text="bad request")


class TestNotifuseLanguageMapping:
    """Tests for the notifuse_language helper."""

    def test_en_passes_through(self) -> None:
        assert notifuse_language("en") == "en"

    def test_es_passes_through(self) -> None:
        assert notifuse_language("es") == "es"

    def test_unknown_locale_falls_back_to_es(self) -> None:
        assert notifuse_language("fr") == "es"

    def test_empty_string_falls_back_to_es(self) -> None:
        assert notifuse_language("") == "es"


class TestEmailTypeValues:
    """Tests for the EmailType enum values matching Notifuse template slugs."""

    def test_verify_email_slug(self) -> None:
        assert EmailType.VERIFY_EMAIL.value == "verify_email"

    def test_reset_password_slug(self) -> None:
        assert EmailType.RESET_PASSWORD.value == "password_reset"

    def test_all_slugs_are_strings(self) -> None:
        for member in EmailType:
            assert isinstance(member.value, str)


class TestNotifuseProviderSend:
    """Tests for NotifuseProvider.send using MockTransport."""

    async def test_posts_to_correct_url_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        await provider.send(
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            template_slug=EmailType.VERIFY_EMAIL.value,
            data={"verify_url": "https://example.com/verify"},
            external_id="ext-001",
        )

        assert len(captured) == 1
        assert captured[0].url.path == "/api/transactional.send"

    async def test_authorization_header_contains_bearer_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        await provider.send(
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            template_slug=EmailType.VERIFY_EMAIL.value,
            data={},
            external_id="ext-002",
        )

        assert captured[0].headers["authorization"] == f"Bearer {API_KEY}"

    async def test_body_contains_workspace_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        await provider.send(
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            template_slug=EmailType.VERIFY_EMAIL.value,
            data={},
            external_id="ext-003",
        )

        body = json.loads(captured[0].content)
        assert body["workspace_id"] == WORKSPACE_ID

    async def test_notification_id_matches_template_slug(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        slug = EmailType.RESET_PASSWORD.value
        await provider.send(
            to_email="user@example.com",
            first_name="Bob",
            locale="es",
            template_slug=slug,
            data={"reset_url": "https://example.com/reset"},
            external_id="ext-004",
        )

        body = json.loads(captured[0].content)
        assert body["notification"]["id"] == slug

    async def test_channels_is_email_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        await provider.send(
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            template_slug=EmailType.VERIFY_EMAIL.value,
            data={},
            external_id="ext-005",
        )

        body = json.loads(captured[0].content)
        assert body["notification"]["channels"] == ["email"]

    async def test_contact_language_mapped_from_locale(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        await provider.send(
            to_email="user@example.com",
            first_name="Carlos",
            locale="es",
            template_slug=EmailType.VERIFY_EMAIL.value,
            data={},
            external_id="ext-006",
        )

        body = json.loads(captured[0].content)
        assert body["notification"]["contact"]["language"] == "es"

    async def test_first_name_fallback_to_email_local_part(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        await provider.send(
            to_email="johndoe@example.com",
            first_name="",
            locale="en",
            template_slug=EmailType.VERIFY_EMAIL.value,
            data={},
            external_id="ext-007",
        )

        body = json.loads(captured[0].content)
        assert body["notification"]["contact"]["first_name"] == "johndoe"

    async def test_data_passed_through_to_notification(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        template_data = {"verify_url": "https://example.com/v", "expiry_hours": 24}
        await provider.send(
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            template_slug=EmailType.VERIFY_EMAIL.value,
            data=template_data,
            external_id="ext-008",
        )

        body = json.loads(captured[0].content)
        assert body["notification"]["data"] == template_data

    async def test_non_2xx_raises_email_delivery_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        provider = _make_provider(_error_handler)

        with pytest.raises(EmailDeliveryError) as exc_info:
            await provider.send(
                to_email="user@example.com",
                first_name="Alice",
                locale="en",
                template_slug=EmailType.VERIFY_EMAIL.value,
                data={},
                external_id="ext-009",
            )

        assert "400" in str(exc_info.value)

    async def test_transport_exception_raises_email_delivery_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        def raising_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        provider = _make_provider(raising_handler)

        with pytest.raises(EmailDeliveryError):
            await provider.send(
                to_email="user@example.com",
                first_name="Alice",
                locale="en",
                template_slug=EmailType.VERIFY_EMAIL.value,
                data={},
                external_id="ext-010",
            )

    async def test_external_id_in_notification_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        await provider.send(
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            template_slug=EmailType.VERIFY_EMAIL.value,
            data={},
            external_id="idempotency-key-xyz",
        )

        body = json.loads(captured[0].content)
        assert body["notification"]["external_id"] == "idempotency-key-xyz"

    async def test_api_key_not_present_in_request_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_BASE_URL", BASE_URL)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_API_KEY", API_KEY)
        monkeypatch.setattr("ai_shop_helper_backend.services.email.provider.settings.NOTIFUSE_WORKSPACE_ID", WORKSPACE_ID)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={})

        provider = _make_provider(handler)
        await provider.send(
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            template_slug=EmailType.VERIFY_EMAIL.value,
            data={},
            external_id="ext-012",
        )

        body_str = captured[0].content.decode()
        assert API_KEY not in body_str
