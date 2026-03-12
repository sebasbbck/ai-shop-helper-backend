from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.deps import (
    CurrentSuperUser,
    PaginationDep,
    SessionDep,
)
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.schemas.project_types import (
    ProjectTypeCreate,
    ProjectTypePublic,
    ProjectTypeUpdate,
)
from ai_shop_helper_backend.services import project_types

router = APIRouter(prefix="/project-types", tags=["project-types"])


@router.post("/", response_model=ProjectTypePublic, status_code=status.HTTP_201_CREATED)
async def create_project_type(
    project_type_in: ProjectTypeCreate,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> ProjectTypePublic:
    """Create a new project type. Superuser only.

    Args:
        project_type_in (ProjectTypeCreate): The project type data.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        ProjectTypePublic: The created project type.

    Raises:
        HTTPException: 409 if the project type name is already registered.
    """
    if await project_types.get_project_type_by_name(session, project_type_in.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project type name already registered",
        )
    project_type = await project_types.create_project_type(
        session, project_type_in, current_superuser.id
    )
    return ProjectTypePublic.model_validate(project_type)


@router.get("/", response_model=PaginatedResponse[ProjectTypePublic])
async def get_project_types(
    current_superuser: CurrentSuperUser,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[ProjectTypePublic]:
    """Get a paginated list of project types. Superuser only.

    Args:
        current_superuser (User): The current superuser.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.

    Returns:
        PaginatedResponse[ProjectTypePublic]: The paginated list of project types.
    """
    items, total = await project_types.get_project_types(
        session, pagination.offset, pagination.limit
    )
    return PaginatedResponse(
        items=[ProjectTypePublic.model_validate(pt) for pt in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{project_type_id}", response_model=ProjectTypePublic)
async def get_project_type(
    project_type_id: UUID,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> ProjectTypePublic:
    """Get a project type by ID. Superuser only.

    Args:
        project_type_id (UUID): The project type ID.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        ProjectTypePublic: The project type.

    Raises:
        HTTPException: 404 if the project type does not exist.
    """
    project_type = await project_types.get_project_type_by_id(session, project_type_id)
    if not project_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project type not found",
        )
    return ProjectTypePublic.model_validate(project_type)


@router.patch("/{project_type_id}", response_model=ProjectTypePublic)
async def update_project_type(
    project_type_id: UUID,
    project_type_in: ProjectTypeUpdate,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> ProjectTypePublic:
    """Update a project type. Superuser only.

    Args:
        project_type_id (UUID): The project type ID.
        project_type_in (ProjectTypeUpdate): The update data.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        ProjectTypePublic: The updated project type.

    Raises:
        HTTPException: 404 if the project type does not exist.
        HTTPException: 409 if the project type name is already registered.
    """
    project_type = await project_types.get_project_type_by_id(session, project_type_id)
    if not project_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project type not found",
        )
    if project_type_in.name:
        await _check_name_available(session, project_type_in.name, project_type.name)
    updated_project_type = await project_types.update_project_type(
        session, project_type, project_type_in, current_superuser.id
    )
    return ProjectTypePublic.model_validate(updated_project_type)


@router.delete("/{project_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_type(
    project_type_id: UUID,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> None:
    """Delete a project type. Superuser only.

    Args:
        project_type_id (UUID): The project type ID.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Raises:
        HTTPException: 404 if the project type does not exist.
    """
    project_type = await project_types.get_project_type_by_id(session, project_type_id)
    if not project_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project type not found",
        )
    await project_types.delete_project_type(session, project_type)


async def _check_name_available(
    session: AsyncSession, name: str, current_name: str
) -> None:
    if name != current_name and await project_types.get_project_type_by_name(
        session, name
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project type name already registered",
        )
