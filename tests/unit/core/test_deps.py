import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pytest_mock import MockerFixture

from ai_shop_helper_backend.core.deps import get_current_superuser, get_current_user
from ai_shop_helper_backend.models import User


class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    async def test_raises_401_on_invalid_token(
        self, mocker: MockerFixture, mock_session: AsyncMock
    ):
        """Test that get_current_user raises 401 if the token is invalid."""
        mocker.patch(
            "ai_shop_helper_backend.core.deps.decode_access_token", return_value=None
        )

        with pytest.raises(HTTPException) as exc:
            await get_current_user(token="bad.token", session=mock_session)

        assert exc.value.status_code == 401

    async def test_raises_401_on_malformed_uuid(
        self, mocker: MockerFixture, mock_session: AsyncMock
    ):
        """Test that get_current_user raises 401 if the token decodes to a non-UUID string."""
        mocker.patch(
            "ai_shop_helper_backend.core.deps.decode_access_token",
            return_value="not-a-uuid",
        )

        with pytest.raises(HTTPException) as exc:
            await get_current_user(token="some-token", session=mock_session)

        assert exc.value.status_code == 401

    async def test_raises_401_when_user_not_found(
        self, mocker: MockerFixture, mock_session: AsyncMock
    ):
        """Test that get_current_user raises 401 if the user ID from the token does not exist in the database."""
        mocker.patch(
            "ai_shop_helper_backend.core.deps.decode_access_token",
            return_value=str(uuid.uuid4()),
        )
        mocker.patch(
            "ai_shop_helper_backend.services.users.get_user_by_id",
            new_callable=AsyncMock,
            return_value=None,
        )

        with pytest.raises(HTTPException) as exc:
            await get_current_user(token="some-token", session=mock_session)

        assert exc.value.status_code == 401

    async def test_raises_403_when_inactive(
        self,
        mocker: MockerFixture,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ):
        """Test that get_current_user raises 403 if the user is inactive."""
        user = make_user(is_active=False)
        mocker.patch(
            "ai_shop_helper_backend.core.deps.decode_access_token",
            return_value=str(user.id),
        )
        mocker.patch(
            "ai_shop_helper_backend.services.users.get_user_by_id",
            new_callable=AsyncMock,
            return_value=user,
        )

        with pytest.raises(HTTPException) as exc:
            await get_current_user(token="some-token", session=mock_session)

        assert exc.value.status_code == 403

    async def test_returns_user_on_valid_token(
        self,
        mocker: MockerFixture,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ):
        """Test that get_current_user returns the user if the token is valid."""
        user = make_user()
        mocker.patch(
            "ai_shop_helper_backend.core.deps.decode_access_token",
            return_value=str(user.id),
        )
        mocker.patch(
            "ai_shop_helper_backend.services.users.get_user_by_id",
            new_callable=AsyncMock,
            return_value=user,
        )

        result = await get_current_user(token="valid-token", session=mock_session)

        assert result is user


class TestGetCurrentSuperuser:
    """Tests for the get_current_superuser dependency."""

    async def test_raises_403_for_regular_user(
        self,
        make_user: Callable[..., User],
    ):
        """Test that get_current_superuser raises 403 if the user is not a superuser."""
        user = make_user(is_superuser=False)

        with pytest.raises(HTTPException) as exc:
            await get_current_superuser(current_user=user)

        assert exc.value.status_code == 403

    async def test_returns_superuser(
        self,
        make_user: Callable[..., User],
    ):
        """Test that get_current_superuser returns the user if they are a superuser."""
        user = make_user(is_superuser=True)

        result = await get_current_superuser(current_user=user)

        assert result is user
