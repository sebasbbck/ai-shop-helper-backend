"""Unit tests for services/agents.py — all DB calls mocked via mock_session."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from ai_shop_helper_backend.models.agents import Agent
from ai_shop_helper_backend.schemas.agents import AgentCreate, AgentUpdate
from ai_shop_helper_backend.services.agents import (
    create_agent,
    delete_agent,
    get_agent_by_id,
    get_agent_by_name,
    get_agents,
    get_agents_by_project_type,
    update_agent,
)


class TestGetAgentById:
    async def test_returns_agent_when_found(self, mock_session: AsyncMock) -> None:
        agent = MagicMock(spec=Agent)
        mock_session.get.return_value = agent

        result = await get_agent_by_id(mock_session, uuid.uuid4())

        assert result is agent

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None

        result = await get_agent_by_id(mock_session, uuid.uuid4())

        assert result is None


class TestGetAgentByName:
    async def test_returns_agent_when_found(self, mock_session: AsyncMock) -> None:
        agent = MagicMock(spec=Agent)
        mock_session.exec.return_value.first.return_value = agent

        result = await get_agent_by_name(mock_session, "my-agent")

        assert result is agent

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        mock_session.exec.return_value.first.return_value = None

        result = await get_agent_by_name(mock_session, "missing")

        assert result is None


class TestGetAgents:
    async def test_returns_paginated_agents_and_count(
        self, mock_session: AsyncMock
    ) -> None:
        agent = MagicMock(spec=Agent)
        count_result = MagicMock()
        count_result.one.return_value = 1
        agents_result = MagicMock()
        agents_result.all.return_value = [agent]
        mock_session.exec.side_effect = [count_result, agents_result]

        items, total = await get_agents(mock_session, offset=0, limit=50)

        assert total == 1
        assert items == [agent]


class TestGetAgentsByProjectType:
    async def test_returns_agents_for_project_type(
        self, mock_session: AsyncMock
    ) -> None:
        agent = MagicMock(spec=Agent)
        mock_session.exec.return_value.all.return_value = [agent]

        result = await get_agents_by_project_type(mock_session, uuid.uuid4())

        assert result == [agent]


class TestCreateAgent:
    async def test_creates_agent_with_correct_fields(
        self, mock_session: AsyncMock
    ) -> None:
        user_id = uuid.uuid4()
        agent_in = AgentCreate(name="Test Agent", description="desc")

        result = await create_agent(mock_session, agent_in, user_id)

        mock_session.add.assert_called_once()
        assert result.name == "Test Agent"
        assert result.created_by == user_id


class TestUpdateAgent:
    async def test_updates_agent_fields(self, mock_session: AsyncMock) -> None:
        agent = MagicMock(spec=Agent)
        user_id = uuid.uuid4()
        agent_in = AgentUpdate(name="Updated Name")

        await update_agent(mock_session, agent, agent_in, user_id)

        mock_session.add.assert_called_once_with(agent)
        assert agent.updated_by == user_id


class TestDeleteAgent:
    async def test_calls_session_delete(self, mock_session: AsyncMock) -> None:
        agent = MagicMock(spec=Agent)

        await delete_agent(mock_session, agent)

        mock_session.delete.assert_called_once_with(agent)
