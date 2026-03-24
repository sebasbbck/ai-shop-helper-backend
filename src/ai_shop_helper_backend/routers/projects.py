from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from ai_shop_helper_backend.core.deps import (
    CurrentOrgAdmin,
    CurrentOrgMember,
    CurrentUser,
    PaginationDep,
    SessionDep,
)
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.schemas.projects import (
    ProjectCreate,
    ProjectPublic,
    ProjectUpdate,
)
from ai_shop_helper_backend.services import project_types, projects

router = APIRouter(prefix="/orgs", tags=["projects"])
user_router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "/{org_id}/projects", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED
)
async def create_project(
    org_id: UUID,
    project_in: ProjectCreate,
    org_admin: CurrentOrgAdmin,
    session: SessionDep,
) -> ProjectPublic:
    """Create a project in the organization. Admin+ only.

    Args:
        org_id (UUID): The organization ID.
        project_in (ProjectCreate): The project data.
        org_admin (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Returns:
        ProjectPublic: The created project.

    Raises:
        HTTPException: 400 if org_id mismatch.
        HTTPException: 404 if project type does not exist.
        HTTPException: 409 if project name already exists in org.
    """
    if project_in.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization ID mismatch",
        )

    project_type = await project_types.get_project_type_by_id(
        session, project_in.project_type_id
    )
    if not project_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project type not found",
        )

    if await projects.get_project_by_name_and_org(session, org_id, project_in.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project name already exists in this organization",
        )

    project = await projects.create_project(session, project_in, org_admin[0].id)
    return ProjectPublic.model_validate(project)


@router.get("/{org_id}/projects", response_model=PaginatedResponse[ProjectPublic])
async def get_org_projects(
    org_id: UUID,
    org_member: CurrentOrgMember,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[ProjectPublic]:
    """List organization projects. Member access.

    Args:
        org_id (UUID): The organization ID.
        org_member (tuple[User, OrgUser]): The current user and their org membership.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.

    Returns:
        PaginatedResponse[ProjectPublic]: The paginated list of projects.
    """
    items, total = await projects.get_projects(
        session, org_id, pagination.offset, pagination.limit
    )
    return PaginatedResponse(
        items=[ProjectPublic.model_validate(p) for p in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{org_id}/projects/{project_id}", response_model=ProjectPublic)
async def get_project(
    org_id: UUID,
    project_id: UUID,
    org_member: CurrentOrgMember,
    session: SessionDep,
) -> ProjectPublic:
    """Get project details. Member access.

    Args:
        org_id (UUID): The organization ID.
        project_id (UUID): The project ID.
        org_member (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Returns:
        ProjectPublic: The project.

    Raises:
        HTTPException: 404 if the project does not exist or belongs to a different org.
    """
    project = await projects.get_project_by_id(session, project_id)
    if not project or project.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return ProjectPublic.model_validate(project)


@router.patch("/{org_id}/projects/{project_id}", response_model=ProjectPublic)
async def update_project(
    org_id: UUID,
    project_id: UUID,
    project_in: ProjectUpdate,
    org_admin: CurrentOrgAdmin,
    session: SessionDep,
) -> ProjectPublic:
    """Update project. Admin+ only.

    Args:
        org_id (UUID): The organization ID.
        project_id (UUID): The project ID.
        project_in (ProjectUpdate): The update data.
        org_admin (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Returns:
        ProjectPublic: The updated project.

    Raises:
        HTTPException: 404 if the project does not exist or belongs to a different org, or project type not found.
        HTTPException: 409 if project name already exists in org.
    """
    project = await projects.get_project_by_id(session, project_id)
    if not project or project.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project_in.project_type_id:
        project_type = await project_types.get_project_type_by_id(
            session, project_in.project_type_id
        )
        if not project_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project type not found",
            )

    if project_in.name and project_in.name != project.name:
        if await projects.get_project_by_name_and_org(session, org_id, project_in.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project name already exists in this organization",
            )

    updated_project = await projects.update_project(
        session, project, project_in, org_admin[0].id
    )
    return ProjectPublic.model_validate(updated_project)


@router.delete("/{org_id}/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    org_id: UUID,
    project_id: UUID,
    org_admin: CurrentOrgAdmin,
    session: SessionDep,
) -> None:
    """Delete project. Admin+ only.

    Args:
        org_id (UUID): The organization ID.
        project_id (UUID): The project ID.
        org_admin (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Raises:
        HTTPException: 404 if the project does not exist or belongs to a different org.
    """
    project = await projects.get_project_by_id(session, project_id)
    if not project or project.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    await projects.delete_project(session, project)


@user_router.get("/", response_model=PaginatedResponse[ProjectPublic])
async def get_my_projects(
    current_user: CurrentUser,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[ProjectPublic]:
    """Get all projects the current user has access to across all organizations.

    Args:
        current_user (User): The current authenticated user.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.

    Returns:
        PaginatedResponse[ProjectPublic]: The paginated list of projects.
    """
    items, total = await projects.get_user_projects(
        session, current_user.id, pagination.offset, pagination.limit
    )
    return PaginatedResponse(
        items=[ProjectPublic.model_validate(p) for p in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )
