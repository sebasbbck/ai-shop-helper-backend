from collections.abc import Sequence
from uuid import UUID

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.models.project_types import ProjectType
from ai_shop_helper_backend.schemas.project_types import (
    ProjectTypeCreate,
    ProjectTypeUpdate,
)


async def get_project_type_by_id(
    session: AsyncSession, project_type_id: UUID
) -> ProjectType | None:
    """Get a project type by ID.

    Args:
        session (AsyncSession): The database session.
        project_type_id (UUID): The project type ID.

    Returns:
        ProjectType | None: The project type if found, None otherwise.
    """
    return await session.get(ProjectType, project_type_id)


async def get_project_type_by_name(
    session: AsyncSession, name: str
) -> ProjectType | None:
    """Get a project type by name.

    Args:
        session (AsyncSession): The database session.
        name (str): The project type name.

    Returns:
        ProjectType | None: The project type if found, None otherwise.
    """
    result = await session.exec(select(ProjectType).where(ProjectType.name == name))
    return result.first()


async def get_project_types(
    session: AsyncSession,
    offset: int,
    limit: int,
) -> tuple[Sequence[ProjectType], int]:
    """Get a paginated list of project types.

    Args:
        session (AsyncSession): The database session.
        offset (int): The number of project types to skip.
        limit (int): The maximum number of project types to return.

    Returns:
        tuple[Sequence[ProjectType], int]: A tuple containing the list of project types and the total count.
    """
    total_result = await session.exec(select(func.count()).select_from(ProjectType))
    project_types_result = await session.exec(
        select(ProjectType).offset(offset).limit(limit)
    )
    return project_types_result.all(), total_result.one()


async def create_project_type(
    session: AsyncSession, project_type_in: ProjectTypeCreate, user_id: UUID
) -> ProjectType:
    """Create a new project type.

    Args:
        session (AsyncSession): The database session.
        project_type_in (ProjectTypeCreate): The project type data.
        user_id (UUID): The ID of the user creating the project type.

    Returns:
        ProjectType: The created project type.
    """
    project_type = ProjectType(
        name=project_type_in.name,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(project_type)
    return project_type


async def update_project_type(
    session: AsyncSession,
    project_type: ProjectType,
    project_type_in: ProjectTypeUpdate,
    user_id: UUID,
) -> ProjectType:
    """Update a project type.

    Args:
        session (AsyncSession): The database session.
        project_type (ProjectType): The project type to update.
        project_type_in (ProjectTypeUpdate): The update data.
        user_id (UUID): The ID of the user updating the project type.

    Returns:
        ProjectType: The updated project type.
    """
    data = project_type_in.model_dump(exclude_unset=True)
    project_type.sqlmodel_update(data)
    project_type.updated_by = user_id
    session.add(project_type)
    return project_type


async def delete_project_type(
    session: AsyncSession, project_type: ProjectType
) -> None:
    """Delete a project type.

    Args:
        session (AsyncSession): The database session.
        project_type (ProjectType): The project type to delete.
    """
    await session.delete(project_type)
