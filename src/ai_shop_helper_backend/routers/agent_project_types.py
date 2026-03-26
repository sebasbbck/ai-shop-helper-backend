from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from ai_shop_helper_backend.core.deps import (
    CurrentSuperUser,
    PaginationDep,
    SessionDep,
)
from ai_shop_helper_backend.schemas.agent_project_types import (
    AgentProjectTypeCreate,
    AgentProjectTypePublic,
)
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.services import agent_project_types, agents, project_types

router = APIRouter(prefix="/agent-project-types", tags=["agent-project-types"])


@router.post(
    "/", response_model=AgentProjectTypePublic, status_code=status.HTTP_201_CREATED
)
async def create_agent_project_type(
    apt_in: AgentProjectTypeCreate,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> AgentProjectTypePublic:
    """Create a new agent-project type relationship. Superuser only.

    Args:
        apt_in (AgentProjectTypeCreate): The relationship data.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        AgentProjectTypePublic: The created relationship.

    Raises:
        HTTPException: 404 if agent or project type does not exist.
        HTTPException: 409 if the relationship already exists.
    """
    agent = await agents.get_agent_by_id(session, apt_in.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    project_type = await project_types.get_project_type_by_id(
        session, apt_in.project_type_id
    )
    if not project_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project type not found",
        )

    existing = await agent_project_types.get_agent_project_type_by_combination(
        session, apt_in.agent_id, apt_in.project_type_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent-project type relationship already exists",
        )

    apt = await agent_project_types.create_agent_project_type(
        session, apt_in, current_superuser.id
    )
    return AgentProjectTypePublic.model_validate(apt)


@router.get("/", response_model=PaginatedResponse[AgentProjectTypePublic])
async def get_agent_project_types(
    current_superuser: CurrentSuperUser,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[AgentProjectTypePublic]:
    """Get a paginated list of agent-project type relationships. Superuser only.

    Args:
        current_superuser (User): The current superuser.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.

    Returns:
        PaginatedResponse[AgentProjectTypePublic]: The paginated list of relationships.
    """
    items, total = await agent_project_types.get_agent_project_types(
        session, pagination.offset, pagination.limit
    )
    return PaginatedResponse(
        items=[AgentProjectTypePublic.model_validate(apt) for apt in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{apt_id}", response_model=AgentProjectTypePublic)
async def get_agent_project_type(
    apt_id: UUID,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> AgentProjectTypePublic:
    """Get an agent-project type relationship by ID. Superuser only.

    Args:
        apt_id (UUID): The relationship ID.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        AgentProjectTypePublic: The relationship.

    Raises:
        HTTPException: 404 if the relationship does not exist.
    """
    apt = await agent_project_types.get_agent_project_type_by_id(session, apt_id)
    if not apt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent-project type relationship not found",
        )
    return AgentProjectTypePublic.model_validate(apt)


@router.delete("/{apt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_project_type(
    apt_id: UUID,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> None:
    """Delete an agent-project type relationship. Superuser only.

    Args:
        apt_id (UUID): The relationship ID.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Raises:
        HTTPException: 404 if the relationship does not exist.
    """
    apt = await agent_project_types.get_agent_project_type_by_id(session, apt_id)
    if not apt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent-project type relationship not found",
        )
    await agent_project_types.delete_agent_project_type(session, apt)
