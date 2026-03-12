from collections.abc import Sequence
from uuid import UUID

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.models.agents import Agent
from ai_shop_helper_backend.schemas.agents import AgentCreate, AgentUpdate


async def get_agent_by_id(session: AsyncSession, agent_id: UUID) -> Agent | None:
    """Get an agent by ID.

    Args:
        session (AsyncSession): The database session.
        agent_id (UUID): The agent ID.

    Returns:
        Agent | None: The agent if found, None otherwise.
    """
    return await session.get(Agent, agent_id)


async def get_agent_by_name(session: AsyncSession, name: str) -> Agent | None:
    """Get an agent by name.

    Args:
        session (AsyncSession): The database session.
        name (str): The agent name.

    Returns:
        Agent | None: The agent if found, None otherwise.
    """
    result = await session.exec(select(Agent).where(Agent.name == name))
    return result.first()


async def get_agents(
    session: AsyncSession,
    offset: int,
    limit: int,
) -> tuple[Sequence[Agent], int]:
    """Get a paginated list of agents.

    Args:
        session (AsyncSession): The database session.
        offset (int): The number of agents to skip.
        limit (int): The maximum number of agents to return.

    Returns:
        tuple[Sequence[Agent], int]: A tuple containing the list of agents and the total count.
    """
    total_result = await session.exec(select(func.count()).select_from(Agent))
    agents_result = await session.exec(select(Agent).offset(offset).limit(limit))
    return agents_result.all(), total_result.one()


async def create_agent(
    session: AsyncSession, agent_in: AgentCreate, user_id: UUID
) -> Agent:
    """Create a new agent.

    Args:
        session (AsyncSession): The database session.
        agent_in (AgentCreate): The agent data.
        user_id (UUID): The ID of the user creating the agent.

    Returns:
        Agent: The created agent.
    """
    agent = Agent(
        name=agent_in.name,
        description=agent_in.description,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(agent)
    return agent


async def update_agent(
    session: AsyncSession, agent: Agent, agent_in: AgentUpdate, user_id: UUID
) -> Agent:
    """Update an agent.

    Args:
        session (AsyncSession): The database session.
        agent (Agent): The agent to update.
        agent_in (AgentUpdate): The update data.
        user_id (UUID): The ID of the user updating the agent.

    Returns:
        Agent: The updated agent.
    """
    data = agent_in.model_dump(exclude_unset=True)
    agent.sqlmodel_update(data)
    agent.updated_by = user_id
    session.add(agent)
    return agent


async def delete_agent(session: AsyncSession, agent: Agent) -> None:
    """Delete an agent.

    Args:
        session (AsyncSession): The database session.
        agent (Agent): The agent to delete.
    """
    await session.delete(agent)
