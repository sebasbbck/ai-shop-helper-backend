from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.deps import (
    CurrentSuperUser,
    CurrentUser,
    PaginationDep,
    SessionDep,
)
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.schemas.roles import RoleCreate, RolePublic, RoleUpdate
from ai_shop_helper_backend.services import roles

router = APIRouter(prefix="/roles", tags=["roles"])


@router.post("/", response_model=RolePublic, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_in: RoleCreate,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> RolePublic:
    """Create a new role. Superuser only.

    Args:
        role_in (RoleCreate): The role data.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        RolePublic: The created role.

    Raises:
        HTTPException: 409 if the role name is already registered.
    """
    if await roles.get_role_by_name(session, role_in.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role name already registered",
        )
    role = await roles.create_role(session, role_in, current_superuser.id)
    return RolePublic.model_validate(role)


@router.get("/", response_model=PaginatedResponse[RolePublic])
async def get_roles(
    current_user: CurrentUser,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[RolePublic]:
    """Get a paginated list of roles.

    Args:
        current_user (User): The current authenticated user.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.

    Returns:
        PaginatedResponse[RolePublic]: The paginated list of roles.
    """
    items, total = await roles.get_roles(session, pagination.offset, pagination.limit)
    return PaginatedResponse(
        items=[RolePublic.model_validate(r) for r in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{role_id}", response_model=RolePublic)
async def get_role(
    role_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> RolePublic:
    """Get a role by ID.

    Args:
        role_id (UUID): The role ID.
        current_user (User): The current authenticated user.
        session (SessionDep): The database session.

    Returns:
        RolePublic: The role.

    Raises:
        HTTPException: 404 if the role does not exist.
    """
    role = await roles.get_role_by_id(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return RolePublic.model_validate(role)


@router.patch("/{role_id}", response_model=RolePublic)
async def update_role(
    role_id: UUID,
    role_in: RoleUpdate,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> RolePublic:
    """Update a role. Superuser only.

    Args:
        role_id (UUID): The role ID.
        role_in (RoleUpdate): The update data.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        RolePublic: The updated role.

    Raises:
        HTTPException: 404 if the role does not exist.
        HTTPException: 409 if the role name is already registered.
    """
    role = await roles.get_role_by_id(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    if role_in.name:
        await _check_name_available(session, role_in.name, role.name)
    updated_role = await roles.update_role(session, role, role_in, current_superuser.id)
    return RolePublic.model_validate(updated_role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> None:
    """Delete a role. Superuser only.

    Args:
        role_id (UUID): The role ID.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Raises:
        HTTPException: 404 if the role does not exist.
    """
    role = await roles.get_role_by_id(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    await roles.delete_role(session, role)


async def _check_name_available(
    session: AsyncSession, name: str, current_name: str
) -> None:
    if name != current_name and await roles.get_role_by_name(session, name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role name already registered",
        )
