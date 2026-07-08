"""Unit tests for services/project_types.py — all DB calls mocked via mock_session."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from ai_shop_helper_backend.models.project_types import ProjectType
from ai_shop_helper_backend.schemas.project_types import (
    ProjectTypeCreate,
    ProjectTypeUpdate,
)
from ai_shop_helper_backend.services.project_types import (
    create_project_type,
    delete_project_type,
    get_project_type_by_id,
    get_project_type_by_name,
    get_project_types,
    update_project_type,
)


class TestGetProjectTypeById:
    async def test_returns_project_type_when_found(
        self, mock_session: AsyncMock
    ) -> None:
        pt = MagicMock(spec=ProjectType)
        mock_session.get.return_value = pt

        result = await get_project_type_by_id(mock_session, uuid.uuid4())

        assert result is pt

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None

        result = await get_project_type_by_id(mock_session, uuid.uuid4())

        assert result is None


class TestGetProjectTypeByName:
    async def test_returns_project_type_when_found(
        self, mock_session: AsyncMock
    ) -> None:
        pt = MagicMock(spec=ProjectType)
        mock_session.exec.return_value.first.return_value = pt

        result = await get_project_type_by_name(mock_session, "ecommerce")

        assert result is pt

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_project_type_by_name(mock_session, "missing")

        assert result is None


class TestGetProjectTypes:
    async def test_returns_paginated_project_types_and_count(
        self, mock_session: AsyncMock
    ) -> None:
        pt = MagicMock(spec=ProjectType)
        count_result = MagicMock()
        count_result.one.return_value = 5
        pts_result = MagicMock()
        pts_result.all.return_value = [pt]
        mock_session.exec.side_effect = [count_result, pts_result]

        items, total = await get_project_types(mock_session, offset=0, limit=50)

        assert total == 5
        assert items == [pt]


class TestCreateProjectType:
    async def test_creates_project_type_with_correct_fields(
        self, mock_session: AsyncMock
    ) -> None:
        user_id = uuid.uuid4()
        pt_in = ProjectTypeCreate(name="ecommerce")

        result = await create_project_type(mock_session, pt_in, user_id)

        mock_session.add.assert_called_once()
        assert result.name == "ecommerce"
        assert result.created_by == user_id


class TestUpdateProjectType:
    async def test_updates_project_type_fields(self, mock_session: AsyncMock) -> None:
        pt = MagicMock(spec=ProjectType)
        user_id = uuid.uuid4()
        pt_in = ProjectTypeUpdate(name="updated-type")

        await update_project_type(mock_session, pt, pt_in, user_id)

        mock_session.add.assert_called_once_with(pt)
        assert pt.updated_by == user_id


class TestDeleteProjectType:
    async def test_calls_session_delete(self, mock_session: AsyncMock) -> None:
        pt = MagicMock(spec=ProjectType)

        await delete_project_type(mock_session, pt)

        mock_session.delete.assert_called_once_with(pt)
