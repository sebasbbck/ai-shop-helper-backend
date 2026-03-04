"""Unit tests for core/db.py — get_session commit/rollback behaviour."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from ai_shop_helper_backend.core.db import get_session


class TestGetSession:
    """Tests for the get_session dependency, ensuring it yields a session and handles commit/rollback correctly."""

    @pytest.fixture()
    def mock_async_session(self, mocker: MockerFixture) -> MagicMock:
        """Patch AsyncSessionLocal to return a fake async context manager.

        Returns:
            MagicMock: The mocked context manager that will be used in tests.
        """
        mock_cm = MagicMock()
        session = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mocker.patch(
            "ai_shop_helper_backend.core.db.AsyncSessionLocal", return_value=mock_cm
        )
        return session

    async def test_yields_session(self, mock_async_session: MagicMock):
        """Test that get_session yields the session from AsyncSessionLocal."""
        assert (await get_session().__anext__()) is mock_async_session

    async def test_commits_on_success(self, mock_async_session: MagicMock):
        """Test that get_session commits the session if no exceptions occur."""
        gen = get_session()
        await gen.__anext__()
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

        mock_async_session.commit.assert_awaited_once()
        mock_async_session.rollback.assert_not_awaited()

    async def test_rolls_back_on_exception(self, mock_async_session: MagicMock):
        """Test that get_session rolls back the session if an exception occurs."""
        gen = get_session()
        await gen.__anext__()
        with pytest.raises(ValueError):
            await gen.athrow(ValueError("db error"))

        mock_async_session.rollback.assert_awaited_once()
        mock_async_session.commit.assert_not_awaited()
