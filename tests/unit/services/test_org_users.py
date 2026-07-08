"""Unit tests for services/org_users.py — all DB calls mocked via mock_session."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from ai_shop_helper_backend.models.org_users import OrgUser
from ai_shop_helper_backend.schemas.org_users import OrgUserCreate, OrgUserUpdate
from ai_shop_helper_backend.services.org_users import (
    count_org_owners,
    create_org_user,
    delete_org_user,
    get_org_user,
    get_org_user_by_id,
    get_org_users,
    update_org_user,
)


class TestGetOrgUserById:
    async def test_returns_org_user_when_found(self, mock_session: AsyncMock) -> None:
        org_user = MagicMock(spec=OrgUser)
        mock_session.get.return_value = org_user

        result = await get_org_user_by_id(mock_session, uuid.uuid4())

        assert result is org_user

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None

        result = await get_org_user_by_id(mock_session, uuid.uuid4())

        assert result is None


class TestGetOrgUser:
    async def test_returns_membership_when_found(self, mock_session: AsyncMock) -> None:
        org_user = MagicMock(spec=OrgUser)
        mock_session.exec.return_value.first.return_value = org_user

        result = await get_org_user(mock_session, uuid.uuid4(), uuid.uuid4())

        assert result is org_user

    async def test_returns_none_when_not_member(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_org_user(mock_session, uuid.uuid4(), uuid.uuid4())

        assert result is None


class TestGetOrgUsers:
    async def test_returns_paginated_members_and_count(
        self, mock_session: AsyncMock
    ) -> None:
        org_user = MagicMock(spec=OrgUser)
        count_result = MagicMock()
        count_result.one.return_value = 4
        users_result = MagicMock()
        users_result.all.return_value = [org_user]
        mock_session.exec.side_effect = [count_result, users_result]

        items, total = await get_org_users(
            mock_session, uuid.uuid4(), offset=0, limit=50
        )

        assert total == 4
        assert items == [org_user]


class TestCountOrgOwners:
    async def test_returns_owner_count(self, mock_session: AsyncMock) -> None:
        count_result = MagicMock()
        count_result.one.return_value = 1
        mock_session.exec.return_value = count_result

        result = await count_org_owners(mock_session, uuid.uuid4())

        assert result == 1


class TestCreateOrgUser:
    async def test_creates_org_user_with_correct_fields(
        self, mock_session: AsyncMock
    ) -> None:
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        role_id = uuid.uuid4()
        org_user_in = OrgUserCreate(user_id=user_id, org_id=org_id, role_id=role_id)

        result = await create_org_user(mock_session, org_user_in, user_id)

        mock_session.add.assert_called_once()
        assert result.user_id == user_id
        assert result.org_id == org_id
        assert result.created_by == user_id


class TestUpdateOrgUser:
    async def test_updates_org_user_role(self, mock_session: AsyncMock) -> None:
        org_user = MagicMock(spec=OrgUser)
        user_id = uuid.uuid4()
        new_role_id = uuid.uuid4()
        org_user_in = OrgUserUpdate(role_id=new_role_id)

        await update_org_user(mock_session, org_user, org_user_in, user_id)

        mock_session.add.assert_called_once_with(org_user)
        assert org_user.updated_by == user_id


class TestDeleteOrgUser:
    async def test_calls_session_delete(self, mock_session: AsyncMock) -> None:
        org_user = MagicMock(spec=OrgUser)

        await delete_org_user(mock_session, org_user)

        mock_session.delete.assert_called_once_with(org_user)
