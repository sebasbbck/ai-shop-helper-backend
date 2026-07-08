"""Unit tests for services/roles.py — all DB calls mocked via mock_session."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.schemas.roles import RoleCreate, RoleUpdate
from ai_shop_helper_backend.services.roles import (
    create_role,
    delete_role,
    get_role_by_access_level,
    get_role_by_id,
    get_role_by_name,
    get_roles,
    update_role,
)


class TestGetRoleById:
    async def test_returns_role_when_found(self, mock_session: AsyncMock) -> None:
        role = MagicMock(spec=Role)
        mock_session.get.return_value = role

        result = await get_role_by_id(mock_session, uuid.uuid4())

        assert result is role

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None

        result = await get_role_by_id(mock_session, uuid.uuid4())

        assert result is None


class TestGetRoleByName:
    async def test_returns_role_when_found(self, mock_session: AsyncMock) -> None:
        role = MagicMock(spec=Role)
        mock_session.exec.return_value.first.return_value = role

        result = await get_role_by_name(mock_session, "owner")

        assert result is role

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_role_by_name(mock_session, "missing")

        assert result is None


class TestGetRoleByAccessLevel:
    async def test_returns_role_when_found(self, mock_session: AsyncMock) -> None:
        role = MagicMock(spec=Role)
        mock_session.exec.return_value.first.return_value = role

        result = await get_role_by_access_level(mock_session, 0)

        assert result is role

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_role_by_access_level(mock_session, 99)

        assert result is None


class TestGetRoles:
    async def test_returns_paginated_roles_and_count(
        self, mock_session: AsyncMock
    ) -> None:
        role = MagicMock(spec=Role)
        count_result = MagicMock()
        count_result.one.return_value = 2
        roles_result = MagicMock()
        roles_result.all.return_value = [role]
        mock_session.exec.side_effect = [count_result, roles_result]

        items, total = await get_roles(mock_session, offset=0, limit=50)

        assert total == 2
        assert items == [role]


class TestCreateRole:
    async def test_creates_role_with_correct_fields(
        self, mock_session: AsyncMock
    ) -> None:
        user_id = uuid.uuid4()
        role_in = RoleCreate(name="member", access_level=20)

        result = await create_role(mock_session, role_in, user_id)

        mock_session.add.assert_called_once()
        assert result.name == "member"
        assert result.access_level == 20
        assert result.created_by == user_id


class TestUpdateRole:
    async def test_updates_role_fields(self, mock_session: AsyncMock) -> None:
        role = MagicMock(spec=Role)
        user_id = uuid.uuid4()
        role_in = RoleUpdate(name="admin")

        await update_role(mock_session, role, role_in, user_id)

        mock_session.add.assert_called_once_with(role)
        assert role.updated_by == user_id


class TestDeleteRole:
    async def test_calls_session_delete(self, mock_session: AsyncMock) -> None:
        role = MagicMock(spec=Role)

        await delete_role(mock_session, role)

        mock_session.delete.assert_called_once_with(role)
