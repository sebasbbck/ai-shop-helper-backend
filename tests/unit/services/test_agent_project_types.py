"""Unit tests for services/agent_project_types.py — all DB calls mocked."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from ai_shop_helper_backend.models.agent_project_types import AgentProjectType
from ai_shop_helper_backend.schemas.agent_project_types import AgentProjectTypeCreate
from ai_shop_helper_backend.services.agent_project_types import (
    create_agent_project_type,
    delete_agent_project_type,
    get_agent_project_type_by_combination,
    get_agent_project_type_by_id,
    get_agent_project_types,
    get_agent_project_types_by_agent,
    get_agent_project_types_by_project_type,
)


class TestGetAgentProjectTypeById:
    async def test_returns_apt_when_found(self, mock_session: AsyncMock) -> None:
        apt = MagicMock(spec=AgentProjectType)
        mock_session.get.return_value = apt

        result = await get_agent_project_type_by_id(mock_session, uuid.uuid4())

        assert result is apt

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None

        result = await get_agent_project_type_by_id(mock_session, uuid.uuid4())

        assert result is None


class TestGetAgentProjectTypeByCombination:
    async def test_returns_apt_when_found(self, mock_session: AsyncMock) -> None:
        apt = MagicMock(spec=AgentProjectType)
        mock_session.exec.return_value.first.return_value = apt

        result = await get_agent_project_type_by_combination(
            mock_session, uuid.uuid4(), uuid.uuid4()
        )

        assert result is apt

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_agent_project_type_by_combination(
            mock_session, uuid.uuid4(), uuid.uuid4()
        )

        assert result is None


class TestGetAgentProjectTypesByAgent:
    async def test_returns_apts_for_agent(self, mock_session: AsyncMock) -> None:
        apt = MagicMock(spec=AgentProjectType)
        mock_session.exec.return_value.all.return_value = [apt]

        result = await get_agent_project_types_by_agent(mock_session, uuid.uuid4())

        assert result == [apt]


class TestGetAgentProjectTypesByProjectType:
    async def test_returns_apts_for_project_type(self, mock_session: AsyncMock) -> None:
        apt = MagicMock(spec=AgentProjectType)
        mock_session.exec.return_value.all.return_value = [apt]

        result = await get_agent_project_types_by_project_type(
            mock_session, uuid.uuid4()
        )

        assert result == [apt]


class TestGetAgentProjectTypes:
    async def test_returns_paginated_apts_and_count(
        self, mock_session: AsyncMock
    ) -> None:
        apt = MagicMock(spec=AgentProjectType)
        count_result = MagicMock()
        count_result.one.return_value = 1
        apts_result = MagicMock()
        apts_result.all.return_value = [apt]
        mock_session.exec.side_effect = [count_result, apts_result]

        items, total = await get_agent_project_types(mock_session, offset=0, limit=50)

        assert total == 1
        assert items == [apt]


class TestCreateAgentProjectType:
    async def test_creates_apt_with_correct_fields(
        self, mock_session: AsyncMock
    ) -> None:
        user_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        project_type_id = uuid.uuid4()
        apt_in = AgentProjectTypeCreate(
            agent_id=agent_id, project_type_id=project_type_id
        )

        result = await create_agent_project_type(mock_session, apt_in, user_id)

        mock_session.add.assert_called_once()
        assert result.agent_id == agent_id
        assert result.project_type_id == project_type_id
        assert result.created_by == user_id


class TestDeleteAgentProjectType:
    async def test_calls_session_delete(self, mock_session: AsyncMock) -> None:
        apt = MagicMock(spec=AgentProjectType)

        await delete_agent_project_type(mock_session, apt)

        mock_session.delete.assert_called_once_with(apt)
