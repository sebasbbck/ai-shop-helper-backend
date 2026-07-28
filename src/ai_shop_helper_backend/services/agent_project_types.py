from collections.abc import Sequence
from uuid import UUID

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.models.agent_project_types import AgentProjectType
from ai_shop_helper_backend.schemas.agent_project_types import (
    AgentProjectTypeCreate,
)


async def get_agent_project_type_by_id(
    session: AsyncSession, id: UUID
) -> AgentProjectType | None:
    """Get an agent-project type relationship by ID.

    Args:
        session (AsyncSession): The database session.
        id (UUID): The agent-project type relationship ID.

    Returns:
        AgentProjectType | None: The relationship if found, None otherwise.
    """
    return await session.get(AgentProjectType, id)


async def get_agent_project_type_by_combination(
    session: AsyncSession, agent_id: UUID, project_type_id: UUID
) -> AgentProjectType | None:
    """Get an agent-project type relationship by agent and project type.

    Args:
        session (AsyncSession): The database session.
        agent_id (UUID): The agent ID.
        project_type_id (UUID): The project type ID.

    Returns:
        AgentProjectType | None: The relationship if found, None otherwise.
    """
    result = await session.exec(
        select(AgentProjectType).where(
            AgentProjectType.agent_id == agent_id,
            AgentProjectType.project_type_id == project_type_id,
        )
    )
    return result.first()


async def get_agent_project_types_by_agent(
    session: AsyncSession, agent_id: UUID
) -> Sequence[AgentProjectType]:
    """Get all agent-project type relationships for an agent.

    Args:
        session (AsyncSession): The database session.
        agent_id (UUID): The agent ID.

    Returns:
        Sequence[AgentProjectType]: List of relationships for the agent.
    """
    result = await session.exec(
        select(AgentProjectType).where(AgentProjectType.agent_id == agent_id)
    )
    return result.all()


async def get_agent_project_types_by_project_type(
    session: AsyncSession, project_type_id: UUID
) -> Sequence[AgentProjectType]:
    """Get all agent-project type relationships for a project type.

    Args:
        session (AsyncSession): The database session.
        project_type_id (UUID): The project type ID.

    Returns:
        Sequence[AgentProjectType]: List of relationships for the project type.
    """
    result = await session.exec(
        select(AgentProjectType).where(
            AgentProjectType.project_type_id == project_type_id
        )
    )
    return result.all()


async def get_agent_project_types(
    session: AsyncSession,
    offset: int,
    limit: int,
) -> tuple[Sequence[AgentProjectType], int]:
    """Get a paginated list of agent-project type relationships.

    Args:
        session (AsyncSession): The database session.
        offset (int): The number of relationships to skip.
        limit (int): The maximum number of relationships to return.

    Returns:
        tuple[Sequence[AgentProjectType], int]: A tuple containing the list of relationships and the total count.
    """
    total_result = await session.exec(
        select(func.count()).select_from(AgentProjectType)
    )
    apt_result = await session.exec(
        select(AgentProjectType).offset(offset).limit(limit)
    )
    return apt_result.all(), total_result.one()


async def create_agent_project_type(
    session: AsyncSession, apt_in: AgentProjectTypeCreate, user_id: UUID
) -> AgentProjectType:
    """Create a new agent-project type relationship.

    Args:
        session (AsyncSession): The database session.
        apt_in (AgentProjectTypeCreate): The relationship data.
        user_id (UUID): The ID of the user creating the relationship.

    Returns:
        AgentProjectType: The created relationship.
    """
    agent_project_type = AgentProjectType(
        agent_id=apt_in.agent_id,
        project_type_id=apt_in.project_type_id,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(agent_project_type)
    return agent_project_type


async def delete_agent_project_type(
    session: AsyncSession, agent_project_type: AgentProjectType
) -> None:
    """Delete an agent-project type relationship.

    Args:
        session (AsyncSession): The database session.
        agent_project_type (AgentProjectType): The relationship to delete.
    """
    await session.delete(agent_project_type)
