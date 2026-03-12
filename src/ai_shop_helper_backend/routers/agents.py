from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.deps import (
    CurrentSuperUser,
    PaginationDep,
    SessionDep,
)
from ai_shop_helper_backend.schemas.agents import (
    AgentCreate,
    AgentPublic,
    AgentUpdate,
)
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.services import agents

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/", response_model=AgentPublic, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_in: AgentCreate,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> AgentPublic:
    """Create a new agent. Superuser only.

    Args:
        agent_in (AgentCreate): The agent data.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        AgentPublic: The created agent.

    Raises:
        HTTPException: 409 if the agent name is already registered.
    """
    if await agents.get_agent_by_name(session, agent_in.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent name already registered",
        )
    agent = await agents.create_agent(session, agent_in, current_superuser.id)
    return AgentPublic.model_validate(agent)


@router.get("/", response_model=PaginatedResponse[AgentPublic])
async def get_agents(
    current_superuser: CurrentSuperUser,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[AgentPublic]:
    """Get a paginated list of agents. Superuser only.

    Args:
        current_superuser (User): The current superuser.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.

    Returns:
        PaginatedResponse[AgentPublic]: The paginated list of agents.
    """
    items, total = await agents.get_agents(session, pagination.offset, pagination.limit)
    return PaginatedResponse(
        items=[AgentPublic.model_validate(a) for a in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{agent_id}", response_model=AgentPublic)
async def get_agent(
    agent_id: UUID,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> AgentPublic:
    """Get an agent by ID. Superuser only.

    Args:
        agent_id (UUID): The agent ID.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        AgentPublic: The agent.

    Raises:
        HTTPException: 404 if the agent does not exist.
    """
    agent = await agents.get_agent_by_id(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return AgentPublic.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentPublic)
async def update_agent(
    agent_id: UUID,
    agent_in: AgentUpdate,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> AgentPublic:
    """Update an agent. Superuser only.

    Args:
        agent_id (UUID): The agent ID.
        agent_in (AgentUpdate): The update data.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        AgentPublic: The updated agent.

    Raises:
        HTTPException: 404 if the agent does not exist.
        HTTPException: 409 if the agent name is already registered.
    """
    agent = await agents.get_agent_by_id(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    if agent_in.name:
        await _check_name_available(session, agent_in.name, agent.name)
    updated_agent = await agents.update_agent(
        session, agent, agent_in, current_superuser.id
    )
    return AgentPublic.model_validate(updated_agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> None:
    """Delete an agent. Superuser only.

    Args:
        agent_id (UUID): The agent ID.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Raises:
        HTTPException: 404 if the agent does not exist.
    """
    agent = await agents.get_agent_by_id(session, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    await agents.delete_agent(session, agent)


async def _check_name_available(
    session: AsyncSession, name: str, current_name: str
) -> None:
    if name != current_name and await agents.get_agent_by_name(session, name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent name already registered",
        )
