"""Unit tests for services/auth_email.py — session and outbox fully mocked."""

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from ai_shop_helper_backend.core.email_types import EmailType
from ai_shop_helper_backend.models.auth_email import AuthEmailToken
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.services import auth_email
from ai_shop_helper_backend.services.auth_email import (
    PURPOSE_RESET,
    PURPOSE_VERIFY,
    reset_password,
    resend_verification,
    start_password_reset,
    start_verification,
    verify,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_token(
    user_id: uuid.UUID | None = None,
    purpose: str = PURPOSE_VERIFY,
    used_at: datetime | None = None,
    expires_at: datetime | None = None,
    token_value: str = "tok_abc",
    created_at: datetime | None = None,
) -> AuthEmailToken:
    return AuthEmailToken(
        user_id=user_id or uuid.uuid4(),
        token=token_value,
        purpose=purpose,
        expires_at=expires_at or (_utc_now() + timedelta(hours=24)),
        used_at=used_at,
        created_at=created_at or _utc_now(),
    )


class TestStartVerification:
    async def test_creates_verify_token_and_enqueues(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """start_verification adds an AuthEmailToken and enqueues a VERIFY_EMAIL."""
        user = make_user()
        added_objects: list = []
        mock_session.add.side_effect = added_objects.append

        with patch.object(auth_email.outbox, "enqueue", new_callable=AsyncMock) as mock_enqueue:
            await start_verification(mock_session, user, locale="en")

        token_rows = [o for o in added_objects if isinstance(o, AuthEmailToken)]
        assert len(token_rows) == 1
        tok = token_rows[0]
        assert tok.purpose == PURPOSE_VERIFY
        assert str(tok.user_id) == str(user.id)

        mock_enqueue.assert_awaited_once()
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["email_type"] == EmailType.VERIFY_EMAIL
        assert call_kwargs["to_email"] == user.email
        assert call_kwargs["first_name"] == user.name
        assert call_kwargs["external_id"] == tok.token
        assert "verify_url" in call_kwargs["data"]
        assert tok.token in call_kwargs["data"]["verify_url"]
        assert "expiry_hours" in call_kwargs["data"]


class TestVerify:
    async def test_valid_token_marks_user_verified(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """verify sets email_verified=True and used_at on the token."""
        user = make_user()
        tok = _make_token(user_id=user.id)

        exec_result = MagicMock()
        exec_result.first.return_value = tok
        mock_session.exec.return_value = exec_result
        mock_session.get.return_value = user

        result = await verify(mock_session, tok.token)

        assert result.email_verified is True
        assert tok.used_at is not None

    async def test_missing_token_raises_400(self, mock_session: AsyncMock) -> None:
        """verify raises HTTPException(400) when token not found."""
        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_session.exec.return_value = exec_result

        with pytest.raises(HTTPException) as exc_info:
            await verify(mock_session, "nonexistent")
        assert exc_info.value.status_code == 400

    async def test_used_token_raises_400(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """verify raises HTTPException(400) when token already used."""
        tok = _make_token(used_at=_utc_now())
        exec_result = MagicMock()
        exec_result.first.return_value = tok
        mock_session.exec.return_value = exec_result

        with pytest.raises(HTTPException) as exc_info:
            await verify(mock_session, tok.token)
        assert exc_info.value.status_code == 400

    async def test_expired_token_raises_400(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """verify raises HTTPException(400) when token is expired."""
        tok = _make_token(expires_at=_utc_now() - timedelta(seconds=1))
        exec_result = MagicMock()
        exec_result.first.return_value = tok
        mock_session.exec.return_value = exec_result

        with pytest.raises(HTTPException) as exc_info:
            await verify(mock_session, tok.token)
        assert exc_info.value.status_code == 400


class TestResendVerification:
    async def test_unknown_email_does_not_enqueue(
        self, mock_session: AsyncMock
    ) -> None:
        """resend_verification is a no-op when email does not exist."""
        with (
            patch.object(
                auth_email.users_service, "get_user_by_email", new_callable=AsyncMock
            ) as mock_get,
            patch.object(auth_email.outbox, "enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            mock_get.return_value = None
            await resend_verification(mock_session, "ghost@example.com", locale="en")

        mock_enqueue.assert_not_awaited()

    async def test_already_verified_does_not_enqueue(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """resend_verification is a no-op when user is already verified."""
        user = make_user(email_verified=True)
        with (
            patch.object(
                auth_email.users_service, "get_user_by_email", new_callable=AsyncMock
            ) as mock_get,
            patch.object(auth_email.outbox, "enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            mock_get.return_value = user
            await resend_verification(mock_session, user.email, locale="en")

        mock_enqueue.assert_not_awaited()

    async def test_throttled_does_not_enqueue(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """resend_verification is a no-op when throttled."""
        user = make_user()
        with (
            patch.object(
                auth_email.users_service, "get_user_by_email", new_callable=AsyncMock
            ) as mock_get,
            patch.object(auth_email, "_throttled", new_callable=AsyncMock) as mock_throttle,
            patch.object(auth_email.outbox, "enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            mock_get.return_value = user
            mock_throttle.return_value = True
            await resend_verification(mock_session, user.email, locale="en")

        mock_enqueue.assert_not_awaited()

    async def test_happy_path_enqueues(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """resend_verification enqueues when user exists, unverified, and not throttled."""
        user = make_user()
        added_objects: list = []
        mock_session.add.side_effect = added_objects.append

        with (
            patch.object(
                auth_email.users_service, "get_user_by_email", new_callable=AsyncMock
            ) as mock_get,
            patch.object(auth_email, "_throttled", new_callable=AsyncMock) as mock_throttle,
            patch.object(auth_email.outbox, "enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            mock_get.return_value = user
            mock_throttle.return_value = False
            await resend_verification(mock_session, user.email, locale="en")

        mock_enqueue.assert_awaited_once()


class TestThrottled:
    async def test_not_throttled_when_no_recent_tokens(
        self, mock_session: AsyncMock
    ) -> None:
        """_throttled returns False when no tokens exist in the last hour."""
        exec_result = MagicMock()
        exec_result.all.return_value = []
        mock_session.exec.return_value = exec_result

        result = await auth_email._throttled(mock_session, uuid.uuid4(), PURPOSE_VERIFY)
        assert result is False

    async def test_throttled_when_count_at_max(
        self, mock_session: AsyncMock
    ) -> None:
        """_throttled returns True when hourly count >= EMAIL_RESEND_MAX_PER_HOUR."""
        from ai_shop_helper_backend.core.config import settings

        tokens = [
            _make_token(created_at=_utc_now() - timedelta(minutes=i * 5))
            for i in range(settings.EMAIL_RESEND_MAX_PER_HOUR)
        ]
        exec_result = MagicMock()
        exec_result.all.return_value = tokens
        mock_session.exec.return_value = exec_result

        result = await auth_email._throttled(mock_session, uuid.uuid4(), PURPOSE_VERIFY)
        assert result is True

    async def test_throttled_when_within_cooldown(
        self, mock_session: AsyncMock
    ) -> None:
        """_throttled returns True when most recent token is within cooldown window."""
        recent_tok = _make_token(created_at=_utc_now() - timedelta(seconds=10))
        exec_result = MagicMock()
        exec_result.all.return_value = [recent_tok]
        mock_session.exec.return_value = exec_result

        result = await auth_email._throttled(mock_session, uuid.uuid4(), PURPOSE_VERIFY)
        assert result is True

    async def test_not_throttled_after_cooldown(
        self, mock_session: AsyncMock
    ) -> None:
        """_throttled returns False when most recent token is past the cooldown window."""
        from ai_shop_helper_backend.core.config import settings

        old_tok = _make_token(
            created_at=_utc_now() - timedelta(seconds=settings.EMAIL_RESEND_COOLDOWN_S + 5)
        )
        exec_result = MagicMock()
        exec_result.all.return_value = [old_tok]
        mock_session.exec.return_value = exec_result

        result = await auth_email._throttled(mock_session, uuid.uuid4(), PURPOSE_VERIFY)
        assert result is False


class TestStartPasswordReset:
    async def test_unknown_email_does_not_enqueue(
        self, mock_session: AsyncMock
    ) -> None:
        """start_password_reset is a no-op when email not found."""
        with (
            patch.object(
                auth_email.users_service, "get_user_by_email", new_callable=AsyncMock
            ) as mock_get,
            patch.object(auth_email.outbox, "enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            mock_get.return_value = None
            await start_password_reset(mock_session, "ghost@example.com", locale="en")

        mock_enqueue.assert_not_awaited()

    async def test_happy_path_enqueues_reset_email(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """start_password_reset enqueues a RESET_PASSWORD email with reset_url."""
        user = make_user()
        added_objects: list = []
        mock_session.add.side_effect = added_objects.append

        with (
            patch.object(
                auth_email.users_service, "get_user_by_email", new_callable=AsyncMock
            ) as mock_get,
            patch.object(auth_email, "_throttled", new_callable=AsyncMock) as mock_throttle,
            patch.object(auth_email.outbox, "enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            mock_get.return_value = user
            mock_throttle.return_value = False
            await start_password_reset(mock_session, user.email, locale="es")

        mock_enqueue.assert_awaited_once()
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["email_type"] == EmailType.RESET_PASSWORD
        assert "reset_url" in call_kwargs["data"]


class TestResetPassword:
    async def test_valid_token_updates_password_and_revokes_refresh_tokens(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """reset_password changes hashed_password, sets used_at, and calls session.exec(delete(...))."""
        user = make_user()
        old_hash = user.hashed_password
        tok = _make_token(user_id=user.id, purpose=PURPOSE_RESET)

        exec_result = MagicMock()
        exec_result.first.return_value = tok
        mock_session.exec.return_value = exec_result
        mock_session.get.return_value = user

        result = await reset_password(mock_session, tok.token, "NewP@ss123!")

        assert result.hashed_password != old_hash
        assert tok.used_at is not None
        assert mock_session.exec.call_count >= 2

    async def test_invalid_token_raises_400(self, mock_session: AsyncMock) -> None:
        """reset_password raises HTTPException(400) when token not found."""
        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_session.exec.return_value = exec_result

        with pytest.raises(HTTPException) as exc_info:
            await reset_password(mock_session, "bad_token", "NewP@ss!")
        assert exc_info.value.status_code == 400

    async def test_expired_token_raises_400(
        self, mock_session: AsyncMock
    ) -> None:
        """reset_password raises HTTPException(400) when token is expired."""
        tok = _make_token(
            purpose=PURPOSE_RESET,
            expires_at=_utc_now() - timedelta(seconds=1),
        )
        exec_result = MagicMock()
        exec_result.first.return_value = tok
        mock_session.exec.return_value = exec_result

        with pytest.raises(HTTPException) as exc_info:
            await reset_password(mock_session, tok.token, "NewP@ss!")
        assert exc_info.value.status_code == 400

    async def test_used_token_raises_400(self, mock_session: AsyncMock) -> None:
        """reset_password raises HTTPException(400) when token already consumed."""
        tok = _make_token(purpose=PURPOSE_RESET, used_at=_utc_now())
        exec_result = MagicMock()
        exec_result.first.return_value = tok
        mock_session.exec.return_value = exec_result

        with pytest.raises(HTTPException) as exc_info:
            await reset_password(mock_session, tok.token, "NewP@ss!")
        assert exc_info.value.status_code == 400

    async def test_returns_user(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        """reset_password returns the updated User instance."""
        user = make_user()
        tok = _make_token(user_id=user.id, purpose=PURPOSE_RESET)

        exec_result = MagicMock()
        exec_result.first.return_value = tok
        mock_session.exec.return_value = exec_result
        mock_session.get.return_value = user

        result = await reset_password(mock_session, tok.token, "AnotherPass99!")
        assert result is user
