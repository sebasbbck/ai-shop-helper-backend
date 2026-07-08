"""Unit tests for services/orgs.py — all DB calls mocked via mock_session."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.schemas.orgs import OrgCreate, OrgUpdate
from ai_shop_helper_backend.services.orgs import (
    create_org_with_owner,
    delete_org,
    get_org_by_id,
    get_org_by_name,
    get_user_orgs,
    get_user_orgs_with_projects,
    update_org,
)


class TestGetOrgById:
    async def test_returns_org_when_found(self, mock_session: AsyncMock) -> None:
        org = MagicMock(spec=Org)
        mock_session.get.return_value = org

        result = await get_org_by_id(mock_session, uuid.uuid4())

        assert result is org

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None

        result = await get_org_by_id(mock_session, uuid.uuid4())

        assert result is None


class TestGetOrgByName:
    async def test_returns_org_when_found(self, mock_session: AsyncMock) -> None:
        org = MagicMock(spec=Org)
        mock_session.exec.return_value.first.return_value = org

        result = await get_org_by_name(mock_session, "my-org")

        assert result is org

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_org_by_name(mock_session, "missing")

        assert result is None


class TestGetUserOrgs:
    async def test_returns_paginated_orgs_and_count(
        self, mock_session: AsyncMock
    ) -> None:
        org = MagicMock(spec=Org)
        count_result = MagicMock()
        count_result.one.return_value = 2
        orgs_result = MagicMock()
        orgs_result.all.return_value = [org]
        mock_session.exec.side_effect = [count_result, orgs_result]

        items, total = await get_user_orgs(
            mock_session, uuid.uuid4(), offset=0, limit=50
        )

        assert total == 2
        assert items == [org]


class TestCreateOrgWithOwner:
    async def test_creates_org_and_assigns_owner_role(
        self, mock_session: AsyncMock
    ) -> None:
        user_id = uuid.uuid4()
        role_id = uuid.uuid4()
        org_in = OrgCreate(name="Test Org")

        mock_role = MagicMock()
        mock_role.id = role_id

        with (
            patch(
                "ai_shop_helper_backend.services.roles.get_role_by_access_level",
                new=AsyncMock(return_value=mock_role),
            ) as mock_get_role,
            patch(
                "ai_shop_helper_backend.services.org_users.create_org_user",
                new=AsyncMock(return_value=MagicMock()),
            ) as mock_create_org_user,
        ):
            result = await create_org_with_owner(mock_session, org_in, user_id)

        assert result.name == "Test Org"
        assert result.created_by == user_id
        mock_session.flush.assert_called_once()
        mock_get_role.assert_called_once_with(mock_session, 0)
        mock_create_org_user.assert_called_once()

    async def test_raises_when_no_owner_role_configured(
        self, mock_session: AsyncMock
    ) -> None:
        with patch(
            "ai_shop_helper_backend.services.roles.get_role_by_access_level",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(ValueError, match="Owner role"):
                await create_org_with_owner(
                    mock_session, OrgCreate(name="Org"), uuid.uuid4()
                )


class TestUpdateOrg:
    async def test_updates_org_fields(self, mock_session: AsyncMock) -> None:
        org = MagicMock(spec=Org)
        user_id = uuid.uuid4()
        org_in = OrgUpdate(name="Renamed Org")

        await update_org(mock_session, org, org_in, user_id)

        mock_session.add.assert_called_once_with(org)
        assert org.updated_by == user_id


class TestDeleteOrg:
    async def test_calls_session_delete(self, mock_session: AsyncMock) -> None:
        org = MagicMock(spec=Org)

        await delete_org(mock_session, org)

        mock_session.delete.assert_called_once_with(org)


class TestGetUserOrgsWithProjects:
    async def test_returns_orgs_with_projects_when_org_ids_present(
        self, mock_session: AsyncMock
    ) -> None:
        org_id = uuid.uuid4()
        org = MagicMock(spec=Org)
        org.id = org_id

        from ai_shop_helper_backend.models.projects import Project

        project = MagicMock(spec=Project)
        project.org_id = org_id

        count_result = MagicMock()
        count_result.one.return_value = 1
        orgs_result = MagicMock()
        orgs_result.all.return_value = [org]
        projects_result = MagicMock()
        projects_result.all.return_value = [project]
        mock_session.exec.side_effect = [count_result, orgs_result, projects_result]

        items, total = await get_user_orgs_with_projects(
            mock_session, uuid.uuid4(), offset=0, limit=50
        )

        assert total == 1
        assert items == [(org, [project])]

    async def test_returns_orgs_with_empty_projects_when_no_org_ids(
        self, mock_session: AsyncMock
    ) -> None:
        count_result = MagicMock()
        count_result.one.return_value = 0
        orgs_result = MagicMock()
        orgs_result.all.return_value = []
        mock_session.exec.side_effect = [count_result, orgs_result]

        items, total = await get_user_orgs_with_projects(
            mock_session, uuid.uuid4(), offset=0, limit=50
        )

        assert total == 0
        assert items == []
