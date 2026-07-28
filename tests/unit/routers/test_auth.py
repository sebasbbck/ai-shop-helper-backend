"""Unit tests for routers/auth.py — email flows (units 1-6).

Tests the wiring between the auth router handlers and the auth_email service.
Session and auth_email are fully mocked; no live DB required.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, Request, Response

from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.routers.auth import (
    _email_locale,
    forgot_password,
    register,
    resend_verification,
    reset_password,
    verify_email,
)
from ai_shop_helper_backend.schemas.auth import (
    ForgotPasswordRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from ai_shop_helper_backend.schemas.users import UserCreate


def _make_user(**kwargs) -> User:
    from ai_shop_helper_backend.core.security import hash_password

    defaults = {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "name": "Test User",
        "hashed_password": hash_password("password123"),
        "is_active": True,
        "is_superuser": False,
        "email_verified": False,
    }
    defaults.update(kwargs)
    return User(**defaults)


def _make_request(cookies: dict | None = None, accept_language: str = "") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"accept-language", accept_language.encode())]
        if accept_language
        else [],
        "query_string": b"",
    }
    request = Request(scope)
    if cookies:
        scope["headers"].append(
            (b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode())
        )
    return request


class TestEmailLocale:
    """Tests for the _email_locale helper."""

    def test_next_locale_cookie_en(self):
        """NEXT_LOCALE cookie 'en' is returned directly."""
        req = _make_request(cookies={"NEXT_LOCALE": "en"})
        assert _email_locale(req) == "en"

    def test_next_locale_cookie_es(self):
        """NEXT_LOCALE cookie 'es' is returned directly."""
        req = _make_request(cookies={"NEXT_LOCALE": "es"})
        assert _email_locale(req) == "es"

    def test_next_locale_cookie_invalid_falls_through(self):
        """Unknown NEXT_LOCALE value falls through to Accept-Language."""
        req = _make_request(
            cookies={"NEXT_LOCALE": "fr"}, accept_language="en-US,en;q=0.9"
        )
        assert _email_locale(req) == "en"

    def test_accept_language_en_wins(self):
        """Accept-Language starting with 'en' resolves to 'en'."""
        req = _make_request(accept_language="en-GB,en;q=0.8")
        assert _email_locale(req) == "en"

    def test_default_es(self):
        """No cookie, non-en Accept-Language defaults to 'es'."""
        req = _make_request(accept_language="fr-FR")
        assert _email_locale(req) == "es"

    def test_no_headers_defaults_es(self):
        """No cookie, no Accept-Language defaults to 'es'."""
        req = _make_request()
        assert _email_locale(req) == "es"


class TestRegister:
    """Tests for the register handler's email-verification wiring."""

    async def test_calls_start_verification_with_locale(self):
        """register triggers start_verification with the created user and resolved locale."""
        mock_session = AsyncMock()
        user = _make_user(email_verified=False)
        request = _make_request(cookies={"NEXT_LOCALE": "en"})
        user_in = UserCreate(
            email="new@example.com", name="New", password="password123"
        )

        with (
            patch(
                "ai_shop_helper_backend.routers.auth.users.get_user_by_email",
                return_value=None,
            ),
            patch(
                "ai_shop_helper_backend.routers.auth.users.create_user",
                return_value=user,
            ),
            patch(
                "ai_shop_helper_backend.routers.auth.auth_email.start_verification",
                new_callable=AsyncMock,
            ) as mock_start,
        ):
            result = await register(user_in, request, mock_session)

        mock_start.assert_awaited_once_with(mock_session, user, "en")
        assert result.email == user.email

    async def test_returns_user_public(self):
        """register returns UserPublic for the created user."""
        mock_session = AsyncMock()
        user = _make_user(email_verified=False)
        request = _make_request()
        user_in = UserCreate(
            email="new2@example.com", name="New2", password="password123"
        )

        with (
            patch(
                "ai_shop_helper_backend.routers.auth.users.get_user_by_email",
                return_value=None,
            ),
            patch(
                "ai_shop_helper_backend.routers.auth.users.create_user",
                return_value=user,
            ),
            patch(
                "ai_shop_helper_backend.routers.auth.auth_email.start_verification",
                new_callable=AsyncMock,
            ),
        ):
            result = await register(user_in, request, mock_session)

        assert str(result.id) == str(user.id)

    async def test_409_on_duplicate_email(self):
        """register raises 409 when email already exists, without calling start_verification."""
        mock_session = AsyncMock()
        existing_user = _make_user()
        request = _make_request()
        user_in = UserCreate(
            email="existing@example.com", name="Dup", password="password123"
        )

        with (
            patch(
                "ai_shop_helper_backend.routers.auth.users.get_user_by_email",
                return_value=existing_user,
            ),
            patch(
                "ai_shop_helper_backend.routers.auth.auth_email.start_verification",
                new_callable=AsyncMock,
            ) as mock_start,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await register(user_in, request, mock_session)

        assert exc_info.value.status_code == 409
        mock_start.assert_not_awaited()


class TestLogin:
    """Tests for the login handler's email_verified gate."""

    async def test_403_when_email_not_verified(self):
        """login raises 403 with detail 'email_not_verified' when user.email_verified is False."""
        from fastapi.security import OAuth2PasswordRequestForm

        mock_session = AsyncMock()
        unverified_user = _make_user(email_verified=False)
        mock_response = AsyncMock(spec=Response)
        form_data = AsyncMock(spec=OAuth2PasswordRequestForm)
        form_data.username = "test@example.com"
        form_data.password = "password123"

        with patch(
            "ai_shop_helper_backend.routers.auth.users.authenticate",
            return_value=unverified_user,
        ):
            from ai_shop_helper_backend.routers.auth import login

            with pytest.raises(HTTPException) as exc_info:
                await login(mock_response, form_data, mock_session)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "email_not_verified"

    async def test_401_on_bad_credentials(self):
        """login raises 401 when authenticate returns None."""
        from fastapi.security import OAuth2PasswordRequestForm

        mock_session = AsyncMock()
        mock_response = AsyncMock(spec=Response)
        form_data = AsyncMock(spec=OAuth2PasswordRequestForm)
        form_data.username = "bad@example.com"
        form_data.password = "wrong"

        with patch(
            "ai_shop_helper_backend.routers.auth.users.authenticate", return_value=None
        ):
            from ai_shop_helper_backend.routers.auth import login

            with pytest.raises(HTTPException) as exc_info:
                await login(mock_response, form_data, mock_session)

        assert exc_info.value.status_code == 401

    async def test_issues_tokens_when_verified(self):
        """login issues tokens when user.email_verified is True."""
        from fastapi.security import OAuth2PasswordRequestForm

        from ai_shop_helper_backend.schemas.auth import Token

        mock_session = AsyncMock()
        verified_user = _make_user(email_verified=True)
        mock_response = AsyncMock(spec=Response)
        form_data = AsyncMock(spec=OAuth2PasswordRequestForm)
        form_data.username = "test@example.com"
        form_data.password = "password123"

        expected_token = Token(access_token="tok123")

        with (
            patch(
                "ai_shop_helper_backend.routers.auth.users.authenticate",
                return_value=verified_user,
            ),
            patch(
                "ai_shop_helper_backend.routers.auth.issue_session",
                new_callable=AsyncMock,
                return_value=expected_token,
            ),
        ):
            from ai_shop_helper_backend.routers.auth import login

            result = await login(mock_response, form_data, mock_session)

        assert result.access_token == "tok123"


class TestVerifyEmail:
    """Tests for the verify_email endpoint."""

    async def test_calls_verify_and_returns_message(self):
        """verify_email calls auth_email.verify and returns 'Email verified'."""
        mock_session = AsyncMock()
        body = VerifyEmailRequest(token="good-token")

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.verify",
            new_callable=AsyncMock,
        ) as mock_verify:
            result = await verify_email(body, mock_session)

        mock_verify.assert_awaited_once_with(mock_session, "good-token")
        assert result.message == "Email verified"

    async def test_propagates_400_on_bad_token(self):
        """verify_email propagates 400 from auth_email.verify on invalid token."""
        mock_session = AsyncMock()
        body = VerifyEmailRequest(token="bad-token")

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.verify",
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=400, detail="Invalid or expired token"
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await verify_email(body, mock_session)

        assert exc_info.value.status_code == 400


class TestResendVerification:
    """Tests for the resend_verification endpoint."""

    async def test_always_returns_generic_message(self):
        """resend_verification always returns the same generic message regardless of outcome."""
        mock_session = AsyncMock()
        body = ResendVerificationRequest(email="any@example.com")
        request = _make_request(cookies={"NEXT_LOCALE": "es"})

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.resend_verification",
            new_callable=AsyncMock,
        ) as mock_resend:
            result = await resend_verification(body, request, mock_session)

        mock_resend.assert_awaited_once_with(mock_session, "any@example.com", "es")
        assert "If an account exists" in result.message

    async def test_returns_200_even_when_email_not_found(self):
        """resend_verification returns generic 200 even if no account exists (service returns None)."""
        mock_session = AsyncMock()
        body = ResendVerificationRequest(email="ghost@example.com")
        request = _make_request()

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.resend_verification",
            new_callable=AsyncMock,
        ):
            result = await resend_verification(body, request, mock_session)

        assert result.message is not None

    async def test_locale_passed_to_service(self):
        """resend_verification resolves locale from request and passes it to the service."""
        mock_session = AsyncMock()
        body = ResendVerificationRequest(email="x@example.com")
        request = _make_request(accept_language="en-US")

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.resend_verification",
            new_callable=AsyncMock,
        ) as mock_resend:
            await resend_verification(body, request, mock_session)

        assert mock_resend.call_args.args[2] == "en"


class TestForgotPassword:
    """Tests for the forgot_password endpoint."""

    async def test_always_returns_generic_message(self):
        """forgot_password always returns the same generic message."""
        mock_session = AsyncMock()
        body = ForgotPasswordRequest(email="any@example.com")
        request = _make_request(cookies={"NEXT_LOCALE": "en"})

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.start_password_reset",
            new_callable=AsyncMock,
        ) as mock_reset:
            result = await forgot_password(body, request, mock_session)

        mock_reset.assert_awaited_once_with(mock_session, "any@example.com", "en")
        assert "If an account exists" in result.message

    async def test_returns_200_for_nonexistent_email(self):
        """forgot_password returns generic 200 even if no account exists."""
        mock_session = AsyncMock()
        body = ForgotPasswordRequest(email="nobody@example.com")
        request = _make_request()

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.start_password_reset",
            new_callable=AsyncMock,
        ):
            result = await forgot_password(body, request, mock_session)

        assert result.message is not None

    async def test_locale_passed_to_service(self):
        """forgot_password resolves locale from request and passes it to the service."""
        mock_session = AsyncMock()
        body = ForgotPasswordRequest(email="x@example.com")
        request = _make_request(cookies={"NEXT_LOCALE": "es"})

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.start_password_reset",
            new_callable=AsyncMock,
        ) as mock_reset:
            await forgot_password(body, request, mock_session)

        assert mock_reset.call_args.args[2] == "es"


class TestResetPassword:
    """Tests for the reset_password endpoint."""

    async def test_calls_reset_password_and_returns_message(self):
        """reset_password calls auth_email.reset_password and returns 'Password updated'."""
        mock_session = AsyncMock()
        body = ResetPasswordRequest(token="good-token", new_password="newpassword1")

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.reset_password",
            new_callable=AsyncMock,
        ) as mock_reset:
            result = await reset_password(body, mock_session)

        mock_reset.assert_awaited_once_with(mock_session, "good-token", "newpassword1")
        assert result.message == "Password updated"

    async def test_propagates_400_on_bad_token(self):
        """reset_password propagates 400 from auth_email.reset_password on invalid token."""
        mock_session = AsyncMock()
        body = ResetPasswordRequest(token="expired-token", new_password="newpassword1")

        with patch(
            "ai_shop_helper_backend.routers.auth.auth_email.reset_password",
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=400, detail="Invalid or expired token"
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await reset_password(body, mock_session)

        assert exc_info.value.status_code == 400
