import uuid
from unittest.mock import AsyncMock

from ai_shop_helper_backend.models.google_account import GoogleAccount
from ai_shop_helper_backend.services.google_auth import (
    build_auth_url,
    get_account_by_google_id,
    link_account,
)


class TestBuildAuthUrl:
    def test_includes_login_scopes_only(self) -> None:
        url = build_auth_url("state-token")

        assert "state=state-token" in url
        assert "openid" in url
        assert "analytics.readonly" not in url
        assert "webmasters.readonly" not in url


class TestGetAccountByGoogleId:
    async def test_returns_account_when_found(self, mock_session: AsyncMock) -> None:
        account = GoogleAccount(
            user_id=uuid.uuid4(), google_id="g-123", google_email="a@example.com"
        )
        mock_session.exec.return_value.first.return_value = account

        result = await get_account_by_google_id(mock_session, "g-123")

        assert result is account

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_account_by_google_id(mock_session, "g-404")

        assert result is None


class TestLinkAccount:
    async def test_adds_account_to_session(self, mock_session: AsyncMock) -> None:
        user_id = uuid.uuid4()

        result = await link_account(mock_session, user_id, "g-123", "a@example.com")

        mock_session.add.assert_called_once()
        assert result.user_id == user_id
        assert result.google_id == "g-123"
        assert result.google_email == "a@example.com"
