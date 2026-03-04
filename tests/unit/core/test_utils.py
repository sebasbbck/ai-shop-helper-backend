"""Unit tests for core/utils.py."""

from datetime import UTC, datetime

import pytest

from ai_shop_helper_backend.core.utils import get_datetime_utc, parse_urls


class TestGetDatetimeUtc:
    """Tests for get_datetime_utc function."""

    def test_returns_datetime(self):
        """Test that the function returns a datetime object."""
        assert isinstance(get_datetime_utc(), datetime)

    def test_is_timezone_aware(self):
        """Test that the function returns a timezone-aware datetime object."""
        assert get_datetime_utc().tzinfo is not None

    def test_is_utc(self):
        """Test that the function returns a datetime object in UTC timezone."""
        assert get_datetime_utc().tzinfo == UTC


class TestParseUrls:
    """Tests for parse_urls function."""

    @pytest.mark.parametrize(
        "input,expected",
        [
            ("https://a.com,https://b.com", ["https://a.com", "https://b.com"]),
            (["https://a.com", "https://b.com"], ["https://a.com", "https://b.com"]),
            ("https://a.com , https://b.com", ["https://a.com", "https://b.com"]),
            ("https://a.com/", ["https://a.com"]),
            ("https://a.com,,https://b.com", ["https://a.com", "https://b.com"]),
            ("", []),
            ([], []),
        ],
    )
    def test_splits_comma_separated_string(
        self, input: str | list[str], expected: list[str]
    ):
        """Test that the function returns a list of URLs from a list or comma-separated string."""
        assert parse_urls(input) == expected
