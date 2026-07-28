from collections.abc import Sequence
from uuid import UUID

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.schemas.roles import RoleCreate, RoleUpdate


async def get_role_by_id(session: AsyncSession, role_id: UUID) -> Role | None:
    """Get a role by ID.

    Args:
        session (AsyncSession): The database session.
        role_id (UUID): The role ID.

    Returns:
        Role | None: The role if found, None otherwise.
    """
    return await session.get(Role, role_id)


async def get_role_by_name(session: AsyncSession, name: str) -> Role | None:
    """Get a role by name.

    Args:
        session (AsyncSession): The database session.
        name (str): The role name.

    Returns:
        Role | None: The role if found, None otherwise.
    """
    result = await session.exec(select(Role).where(Role.name == name))
    return result.first()


async def get_role_by_access_level(
    session: AsyncSession, access_level: int
) -> Role | None:
    """Get a role by access level.

    Args:
        session (AsyncSession): The database session.
        access_level (int): The access level (0=owner, 10=admin, etc).

    Returns:
        Role | None: The role if found, None otherwise.
    """
    result = await session.exec(select(Role).where(Role.access_level == access_level))
    return result.first()


async def get_roles(
    session: AsyncSession,
    offset: int,
    limit: int,
) -> tuple[Sequence[Role], int]:
    """Get a paginated list of roles.

    Args:
        session (AsyncSession): The database session.
        offset (int): The number of roles to skip.
        limit (int): The maximum number of roles to return.

    Returns:
        tuple[Sequence[Role], int]: A tuple containing the list of roles and the total count.
    """
    total_result = await session.exec(select(func.count()).select_from(Role))
    roles_result = await session.exec(select(Role).offset(offset).limit(limit))
    return roles_result.all(), total_result.one()


async def create_role(
    session: AsyncSession, role_in: RoleCreate, user_id: UUID
) -> Role:
    """Create a new role.

    Args:
        session (AsyncSession): The database session.
        role_in (RoleCreate): The role data.
        user_id (UUID): The ID of the user creating the role.

    Returns:
        Role: The created role.
    """
    role = Role(
        name=role_in.name,
        description=role_in.description,
        access_level=role_in.access_level,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(role)
    return role


async def update_role(
    session: AsyncSession, role: Role, role_in: RoleUpdate, user_id: UUID
) -> Role:
    """Update a role.

    Args:
        session (AsyncSession): The database session.
        role (Role): The role to update.
        role_in (RoleUpdate): The update data.
        user_id (UUID): The ID of the user updating the role.

    Returns:
        Role: The updated role.
    """
    data = role_in.model_dump(exclude_unset=True)
    role.sqlmodel_update(data)
    role.updated_by = user_id
    session.add(role)
    return role


async def delete_role(session: AsyncSession, role: Role) -> None:
    """Delete a role.

    Args:
        session (AsyncSession): The database session.
        role (Role): The role to delete.
    """
    await session.delete(role)
