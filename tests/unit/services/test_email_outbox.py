"""Unit tests for services/email/outbox.py — provider and session fully mocked."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_shop_helper_backend.core.email_types import EmailType
from ai_shop_helper_backend.models.auth_email import EmailOutbox
from ai_shop_helper_backend.services.email import outbox
from ai_shop_helper_backend.services.email.outbox import _backoff_seconds
from ai_shop_helper_backend.services.email.provider import EmailDeliveryError


def _make_row(**kwargs) -> EmailOutbox:
    defaults = dict(
        to_email="user@example.com",
        first_name="Alice",
        locale="en",
        email_type="verify-email",
        data_json=json.dumps({"verify_url": "http://example.com/verify"}),
        external_id="ext-001",
        status="pending",
        attempts=0,
        next_attempt_at=datetime.now(tz=timezone.utc),
        last_error=None,
        sent_at=None,
    )
    defaults.update(kwargs)
    return EmailOutbox(**defaults)


class TestEnqueue:
    async def test_builds_pending_row_and_adds_to_session(
        self, mock_session: AsyncMock
    ) -> None:
        """enqueue creates an EmailOutbox row with correct fields and calls session.add."""
        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_session.exec.return_value = exec_result
        mock_session.flush = AsyncMock()

        row = await outbox.enqueue(
            mock_session,
            email_type=EmailType.VERIFY_EMAIL,
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            data={"verify_url": "http://example.com/verify"},
            external_id="ext-001",
        )

        assert row.email_type == EmailType.VERIFY_EMAIL.value
        assert row.to_email == "user@example.com"
        assert row.first_name == "Alice"
        assert row.locale == "en"
        assert json.loads(row.data_json) == {"verify_url": "http://example.com/verify"}
        assert row.external_id == "ext-001"
        assert row.status == "pending"
        mock_session.add.assert_called_once_with(row)
        mock_session.flush.assert_awaited_once()

    async def test_idempotent_returns_existing_row_without_adding(
        self, mock_session: AsyncMock
    ) -> None:
        """enqueue returns the existing row when external_id already present; does not add."""
        existing = _make_row()
        exec_result = MagicMock()
        exec_result.first.return_value = existing
        mock_session.exec.return_value = exec_result
        mock_session.flush = AsyncMock()

        result = await outbox.enqueue(
            mock_session,
            email_type=EmailType.VERIFY_EMAIL,
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            data={"verify_url": "http://example.com/verify"},
            external_id="ext-001",
        )

        assert result is existing
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_awaited()

    async def test_stores_none_first_name(self, mock_session: AsyncMock) -> None:
        """enqueue stores first_name=None when not provided."""
        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_session.exec.return_value = exec_result
        mock_session.flush = AsyncMock()

        row = await outbox.enqueue(
            mock_session,
            email_type=EmailType.VERIFY_EMAIL,
            to_email="user@example.com",
            first_name=None,
            locale="en",
            data={},
            external_id="ext-002",
        )

        assert row.first_name is None


class TestDeliverOne:
    async def test_success_marks_sent(self, mock_session: AsyncMock) -> None:
        """deliver_one on provider success sets status='sent' and sent_at, calls provider correctly."""
        row = _make_row()

        with patch.object(outbox, "notifuse_provider") as mock_provider:
            mock_provider.send = AsyncMock()
            await outbox.deliver_one(mock_session, row)

        assert row.status == "sent"
        assert row.sent_at is not None
        mock_provider.send.assert_awaited_once_with(
            to_email="user@example.com",
            first_name="Alice",
            locale="en",
            template_slug="verify-email",
            data={"verify_url": "http://example.com/verify"},
            external_id="ext-001",
        )
        mock_session.add.assert_called_once_with(row)

    async def test_success_uses_empty_string_for_none_first_name(
        self, mock_session: AsyncMock
    ) -> None:
        """deliver_one passes '' to provider when first_name is None."""
        row = _make_row(first_name=None)

        with patch.object(outbox, "notifuse_provider") as mock_provider:
            mock_provider.send = AsyncMock()
            await outbox.deliver_one(mock_session, row)

        _, kwargs = mock_provider.send.call_args
        assert kwargs["first_name"] == ""

    async def test_failure_increments_attempts_and_pushes_next_attempt(
        self, mock_session: AsyncMock
    ) -> None:
        """deliver_one on EmailDeliveryError increments attempts, sets next_attempt_at, stays pending."""
        row = _make_row(attempts=0)
        original_next = row.next_attempt_at

        with patch.object(outbox, "notifuse_provider") as mock_provider:
            mock_provider.send = AsyncMock(side_effect=EmailDeliveryError("timeout"))
            with patch(
                "ai_shop_helper_backend.services.email.outbox.settings"
            ) as mock_settings:
                mock_settings.EMAIL_MAX_ATTEMPTS = 6
                await outbox.deliver_one(mock_session, row)

        assert row.attempts == 1
        assert row.status == "pending"
        assert row.last_error == "timeout"
        assert row.next_attempt_at > original_next

    async def test_failure_at_max_attempts_marks_failed(
        self, mock_session: AsyncMock
    ) -> None:
        """deliver_one at max attempts sets status='failed'."""
        row = _make_row(attempts=5)

        with patch.object(outbox, "notifuse_provider") as mock_provider:
            mock_provider.send = AsyncMock(side_effect=EmailDeliveryError("bad request"))
            with patch(
                "ai_shop_helper_backend.services.email.outbox.settings"
            ) as mock_settings:
                mock_settings.EMAIL_MAX_ATTEMPTS = 6
                await outbox.deliver_one(mock_session, row)

        assert row.status == "failed"
        assert row.attempts == 6

    async def test_failure_does_not_reraise(self, mock_session: AsyncMock) -> None:
        """deliver_one swallows EmailDeliveryError and does not propagate it."""
        row = _make_row()

        with patch.object(outbox, "notifuse_provider") as mock_provider:
            mock_provider.send = AsyncMock(side_effect=EmailDeliveryError("fail"))
            with patch(
                "ai_shop_helper_backend.services.email.outbox.settings"
            ) as mock_settings:
                mock_settings.EMAIL_MAX_ATTEMPTS = 6
                await outbox.deliver_one(mock_session, row)


class TestBackoffSeconds:
    def test_first_attempt_is_sixty_seconds(self) -> None:
        assert _backoff_seconds(1) == 60

    def test_second_attempt_is_one_twenty(self) -> None:
        assert _backoff_seconds(2) == 120

    def test_third_attempt_is_two_forty(self) -> None:
        assert _backoff_seconds(3) == 240

    def test_monotonically_increases_up_to_cap(self) -> None:
        values = [_backoff_seconds(i) for i in range(1, 8)]
        for a, b in zip(values, values[1:]):
            assert b >= a

    def test_capped_at_3600(self) -> None:
        assert _backoff_seconds(100) == 3600

    def test_never_exceeds_cap(self) -> None:
        for i in range(1, 20):
            assert _backoff_seconds(i) <= 3600
