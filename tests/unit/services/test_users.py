"""Unit tests for services/users.py — all DB calls mocked via mock_session."""

import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

from pydantic import SecretStr

from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.schemas.users import UserAdminUpdate, UserCreate, UserUpdate
from ai_shop_helper_backend.services.users import (
    authenticate,
    create_google_user,
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    get_users,
    update_user,
)


class TestGetUserById:
    """Tests for the get_user_by_id service function."""

    async def test_calls_session_get(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ):
        """Test that get_user_by_id calls session.get with the correct parameters and returns the user."""
        user = make_user()
        mock_session.get.return_value = user

        result = await get_user_by_id(mock_session, user.id)

        mock_session.get.assert_called_once_with(User, user.id)
        assert result is user

    async def test_returns_none_when_not_found(
        self,
        mock_session: AsyncMock,
    ):
        """Test that get_user_by_id returns None if the user is not found."""
        mock_session.get.return_value = None

        result = await get_user_by_id(mock_session, uuid.uuid4())

        assert result is None


class TestGetUserByEmail:
    """Tests for the get_user_by_email service function."""

    async def test_returns_user(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ):
        """Test that get_user_by_email returns the user if found."""
        user = make_user()
        mock_session.exec.return_value.first.return_value = user

        result = await get_user_by_email(mock_session, "test@example.com")

        mock_session.exec.assert_called_once()
        assert result is user

    async def test_returns_none_when_not_found(
        self,
        mock_session: AsyncMock,
    ):
        """Test that get_user_by_email returns None if the user is not found."""
        mock_session.exec.return_value.first.return_value = None

        result = await get_user_by_email(mock_session, "nobody@example.com")

        assert result is None


class TestGetUsers:
    """Tests for the get_users service function."""

    async def test_executes_count_and_paginated_queries(
        self, mock_session: AsyncMock, make_user: Callable[..., User]
    ):
        """Test that get_users executes the count query and the paginated query, and returns the correct results."""
        user = make_user()
        count_result = MagicMock()
        count_result.one.return_value = 1
        users_result = MagicMock()
        users_result.all.return_value = [user]
        mock_session.exec.side_effect = [count_result, users_result]

        items, total = await get_users(mock_session, offset=0, limit=50)

        assert mock_session.exec.call_count == 2
        assert total == 1
        assert items == [user]


class TestCreateGoogleUser:
    async def test_creates_user_with_email_and_name(self, mock_session: AsyncMock) -> None:
        result = await create_google_user(mock_session, name="Google User", email="google@example.com")

        mock_session.add.assert_called_once()
        assert result.email == "google@example.com"
        assert result.name == "Google User"

    async def test_sets_random_hashed_password(self, mock_session: AsyncMock) -> None:
        result1 = await create_google_user(mock_session, name="A", email="a@example.com")
        result2 = await create_google_user(mock_session, name="B", email="b@example.com")

        assert result1.hashed_password != "password"
        assert result1.hashed_password != result2.hashed_password


class TestCreateUser:
    """Tests for the create_user service function."""

    async def test_hashes_password_and_adds_to_session(
        self,
        mock_session: AsyncMock,
    ):
        """Test that create_user hashes the password and adds the user to the session."""
        user_in = UserCreate(
            email="new@example.com",
            name="New User",
            password=SecretStr("password123"),
        )

        result = await create_user(mock_session, user_in)

        mock_session.add.assert_called_once()
        assert result.email == "new@example.com"
        assert result.hashed_password != "password123"


class TestAuthenticate:
    """Tests for the authenticate service function."""

    async def test_returns_user_on_valid_credentials(
        self, mock_session: AsyncMock, make_user: Callable[..., User]
    ):
        """Test that authenticate returns the user if the email and password are correct."""
        user = make_user()
        mock_session.exec.return_value.first.return_value = user

        result = await authenticate(mock_session, user.email, "password123")

        assert result is user

    async def test_returns_none_on_wrong_password(
        self, mock_session: AsyncMock, make_user: Callable[..., User]
    ):
        """Test that authenticate returns None if the password is incorrect."""
        user = make_user()
        mock_session.exec.return_value.first.return_value = user

        result = await authenticate(mock_session, user.email, "wrongpassword")

        assert result is None

    async def test_returns_none_for_inactive_user(
        self, mock_session: AsyncMock, make_user: Callable[..., User]
    ):
        """Test that authenticate returns None if the user is inactive."""
        user = make_user(is_active=False)
        mock_session.exec.return_value.first.return_value = user

        result = await authenticate(mock_session, user.email, "password123")

        assert result is None

    async def test_returns_none_for_unknown_email(self, mock_session: AsyncMock):
        """Test that authenticate returns None if the email is not found."""
        mock_session.exec.return_value.first.return_value = None

        result = await authenticate(mock_session, "ghost@example.com", "password123")

        assert result is None


class TestUpdateUser:
    """Tests for the update_user service function."""

    async def test_hashes_password_when_provided(
        self, mock_session: AsyncMock, make_user: Callable[..., User]
    ):
        """Test that update_user hashes the password if a new password is provided."""
        user = make_user()
        user_in = UserUpdate(password=SecretStr("newpassword99"))

        result = await update_user(mock_session, user, user_in)

        mock_session.add.assert_called_once_with(user)
        assert result.hashed_password != "newpassword99"

    async def test_skips_hashing_when_no_password(
        self, mock_session: AsyncMock, make_user: Callable[..., User]
    ):
        """Test that update_user does not change the hashed password if no new password is provided."""
        user = make_user()
        original_hash = user.hashed_password
        user_in = UserUpdate(name="Updated Name")

        result = await update_user(mock_session, user, user_in)

        assert result.name == "Updated Name"
        assert result.hashed_password == original_hash

    async def test_admin_can_set_superuser_flag(
        self, mock_session: AsyncMock, make_user: Callable[..., User]
    ):
        """Test that update_user allows an admin to set the is_superuser flag."""
        user = make_user(is_superuser=False)
        user_in = UserAdminUpdate(is_superuser=True)

        result = await update_user(mock_session, user, user_in)

        assert result.is_superuser is True


class TestDeleteUser:
    """Tests for the delete_user service function."""

    async def test_calls_session_delete(
        self, mock_session: AsyncMock, make_user: Callable[..., User]
    ):
        """Test that delete_user calls session.delete with the correct user."""
        user = make_user()

        await delete_user(mock_session, user)

        mock_session.delete.assert_called_once_with(user)
