"""Unit tests for services/auth.py::issue_session — the shared session-issuing helper
used by password login, refresh, and Google login."""

import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response

from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.services.auth import issue_session


class TestIssueSession:
    async def test_returns_access_token_and_sets_refresh_cookie(
        self, mock_session: AsyncMock, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        mock_session.get.return_value = user
        response = Response()

        token = await issue_session(mock_session, response, user.id)

        assert token.access_token
        assert token.token_type == "bearer"
        mock_session.add.assert_called_once()
        assert "set-cookie" in response.headers

    async def test_raises_when_user_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await issue_session(mock_session, Response(), uuid.uuid4())

        assert exc_info.value.status_code == 401
