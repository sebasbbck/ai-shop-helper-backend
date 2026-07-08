"""Unit tests for services/projects.py — all DB calls mocked via mock_session."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.schemas.projects import ProjectCreate, ProjectUpdate
from ai_shop_helper_backend.services.projects import (
    create_project,
    delete_project,
    get_project_by_id,
    get_project_by_name_and_org,
    get_projects,
    get_user_projects,
    update_project,
)


class TestGetProjectById:
    async def test_returns_project_when_found(self, mock_session: AsyncMock) -> None:
        project = MagicMock(spec=Project)
        mock_session.get.return_value = project

        result = await get_project_by_id(mock_session, uuid.uuid4())

        assert result is project

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None

        result = await get_project_by_id(mock_session, uuid.uuid4())

        assert result is None


class TestGetProjectByNameAndOrg:
    async def test_returns_project_when_found(self, mock_session: AsyncMock) -> None:
        project = MagicMock(spec=Project)
        mock_session.exec.return_value.first.return_value = project

        result = await get_project_by_name_and_org(mock_session, uuid.uuid4(), "proj")

        assert result is project

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_project_by_name_and_org(
            mock_session, uuid.uuid4(), "missing"
        )

        assert result is None


class TestGetProjects:
    async def test_returns_paginated_projects_and_count(
        self, mock_session: AsyncMock
    ) -> None:
        project = MagicMock(spec=Project)
        count_result = MagicMock()
        count_result.one.return_value = 3
        projects_result = MagicMock()
        projects_result.all.return_value = [project]
        mock_session.exec.side_effect = [count_result, projects_result]

        items, total = await get_projects(
            mock_session, uuid.uuid4(), offset=0, limit=50
        )

        assert total == 3
        assert items == [project]


class TestGetUserProjects:
    async def test_returns_user_projects_across_orgs(
        self, mock_session: AsyncMock
    ) -> None:
        project = MagicMock(spec=Project)
        count_result = MagicMock()
        count_result.one.return_value = 1
        projects_result = MagicMock()
        projects_result.all.return_value = [project]
        mock_session.exec.side_effect = [count_result, projects_result]

        items, total = await get_user_projects(mock_session, uuid.uuid4(), 0, 50)

        assert total == 1
        assert items == [project]


class TestCreateProject:
    async def test_creates_project_with_correct_fields(
        self, mock_session: AsyncMock
    ) -> None:
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        type_id = uuid.uuid4()
        project_in = ProjectCreate(
            org_id=org_id, name="My Project", project_type_id=type_id
        )

        result = await create_project(mock_session, project_in, user_id)

        mock_session.add.assert_called_once()
        assert result.name == "My Project"
        assert result.org_id == org_id
        assert result.created_by == user_id


class TestUpdateProject:
    async def test_updates_project_fields(self, mock_session: AsyncMock) -> None:
        project = MagicMock(spec=Project)
        user_id = uuid.uuid4()
        project_in = ProjectUpdate(name="Updated")

        await update_project(mock_session, project, project_in, user_id)

        mock_session.add.assert_called_once_with(project)
        assert project.updated_by == user_id


class TestDeleteProject:
    async def test_calls_session_delete(self, mock_session: AsyncMock) -> None:
        project = MagicMock(spec=Project)

        await delete_project(mock_session, project)

        mock_session.delete.assert_called_once_with(project)
