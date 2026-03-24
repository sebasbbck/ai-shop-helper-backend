from collections.abc import Sequence
from uuid import UUID

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.models.org_users import OrgUser
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.schemas.projects import ProjectCreate, ProjectUpdate


async def get_project_by_id(session: AsyncSession, project_id: UUID) -> Project | None:
    """Get a project by ID.

    Args:
        session (AsyncSession): The database session.
        project_id (UUID): The project ID.

    Returns:
        Project | None: The project if found, None otherwise.
    """
    return await session.get(Project, project_id)


async def get_project_by_name_and_org(
    session: AsyncSession, org_id: UUID, name: str
) -> Project | None:
    """Get a project by name within an organization.

    Args:
        session (AsyncSession): The database session.
        org_id (UUID): The organization ID.
        name (str): The project name.

    Returns:
        Project | None: The project if found, None otherwise.
    """
    result = await session.exec(
        select(Project).where(Project.org_id == org_id, Project.name == name)
    )
    return result.first()


async def get_projects(
    session: AsyncSession,
    org_id: UUID,
    offset: int,
    limit: int,
) -> tuple[Sequence[Project], int]:
    """Get a paginated list of projects in an organization.

    Args:
        session (AsyncSession): The database session.
        org_id (UUID): The organization ID.
        offset (int): The number of projects to skip.
        limit (int): The maximum number of projects to return.

    Returns:
        tuple[Sequence[Project], int]: A tuple containing the list of projects and the total count.
    """
    total_result = await session.exec(
        select(func.count()).select_from(Project).where(Project.org_id == org_id)
    )
    projects_result = await session.exec(
        select(Project).where(Project.org_id == org_id).offset(offset).limit(limit)
    )
    return projects_result.all(), total_result.one()


async def get_user_projects(
    session: AsyncSession,
    user_id: UUID,
    offset: int,
    limit: int,
) -> tuple[Sequence[Project], int]:
    """Get a paginated list of all projects the user has access to across all orgs.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.
        offset (int): The number of projects to skip.
        limit (int): The maximum number of projects to return.

    Returns:
        tuple[Sequence[Project], int]: A tuple containing the list of projects and the total count.
    """
    total_result = await session.exec(
        select(func.count())
        .select_from(Project)
        .join(OrgUser, Project.org_id == OrgUser.org_id)
        .where(OrgUser.user_id == user_id)
    )

    projects_result = await session.exec(
        select(Project)
        .join(OrgUser, Project.org_id == OrgUser.org_id)
        .where(OrgUser.user_id == user_id)
        .offset(offset)
        .limit(limit)
    )
    return projects_result.all(), total_result.one()


async def create_project(
    session: AsyncSession, project_in: ProjectCreate, user_id: UUID
) -> Project:
    """Create a new project.

    Args:
        session (AsyncSession): The database session.
        project_in (ProjectCreate): The project data.
        user_id (UUID): The ID of the user creating the project.

    Returns:
        Project: The created project.
    """
    project = Project(
        org_id=project_in.org_id,
        name=project_in.name,
        project_type_id=project_in.project_type_id,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(project)
    return project


async def update_project(
    session: AsyncSession, project: Project, project_in: ProjectUpdate, user_id: UUID
) -> Project:
    """Update a project.

    Args:
        session (AsyncSession): The database session.
        project (Project): The project to update.
        project_in (ProjectUpdate): The update data.
        user_id (UUID): The ID of the user updating the project.

    Returns:
        Project: The updated project.
    """
    data = project_in.model_dump(exclude_unset=True)
    project.sqlmodel_update(data)
    project.updated_by = user_id
    session.add(project)
    return project


async def delete_project(session: AsyncSession, project: Project) -> None:
    """Delete a project.

    Args:
        session (AsyncSession): The database session.
        project (Project): The project to delete.
    """
    await session.delete(project)
