"""Unit tests for core/security.py — pure functions, no DB."""

from datetime import UTC, datetime

import jwt
import pytest

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    refresh_token_expiry,
    verify_password,
)
from ai_shop_helper_backend.core.utils import get_datetime_utc


class TestHashPassword:
    """Tests for the hash_password and verify_password functions."""

    def test_is_not_plain(self):
        """Test that the hashed password is not the same as the plain password."""
        hashed = hash_password("mysecretpassword")
        assert hashed != "mysecretpassword"
        assert len(hashed)

    def test_verify_correct(self):
        """Test that verify_password returns True for the correct password."""
        hashed = hash_password("mysecretpassword")
        assert verify_password("mysecretpassword", hashed) is True

    def test_verify_wrong(self):
        """Test that verify_password returns False for an incorrect password."""
        hashed = hash_password("mysecretpassword")
        assert verify_password("wrongpassword", hashed) is False


class TestAccessToken:
    """Tests for the create_access_token and decode_access_token functions."""

    @pytest.mark.parametrize("subject", ["uuid-1234", "some-other-sub"])
    def test_create_returns_decodable_jwt(self, subject: str):
        """Test that the subject is correctly encoded in the token."""
        token = create_access_token(subject, False)
        assert decode_access_token(token) == subject

    def test_decode_expired_returns_none(self):
        """Test that decoding an expired token returns None."""
        expired_payload = {
            "sub": "user-123",
            "exp": datetime(2000, 1, 1, tzinfo=UTC),
        }
        token = jwt.encode(
            expired_payload, settings.SECRET_KEY, algorithm=settings.KEY_ALGORITHM
        )
        assert decode_access_token(token) is None

    def test_decode_tampered_returns_none(self):
        """Test that decoding a tampered token returns None."""
        token = create_access_token("user-123", False)
        assert decode_access_token(token + "tampered") is None

    @pytest.mark.parametrize("is_superuser", [True, False])
    def test_create_includes_is_superuser(self, is_superuser: bool):
        """Test that is_superuser is correctly encoded in the token."""
        token = create_access_token("user-123", is_superuser)
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.KEY_ALGORITHM]
        )
        assert payload["is_superuser"] == is_superuser


class TestRefreshToken:
    """Tests for the generate_refresh_token and refresh_token_expiry functions."""

    def test_generate_is_nonempty_string(self):
        """Test that the generated refresh token is a non-empty string."""
        token = generate_refresh_token()
        assert len(token)

    def test_generate_is_unique(self):
        """Test that multiple calls to generate_refresh_token produce different tokens."""
        assert generate_refresh_token() != generate_refresh_token()

    def test_expiry_is_in_future(self):
        """Test that the refresh token expiry is in the future."""
        assert refresh_token_expiry() > get_datetime_utc()
