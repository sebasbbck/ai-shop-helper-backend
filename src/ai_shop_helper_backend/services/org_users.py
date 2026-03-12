from collections.abc import Sequence
from uuid import UUID

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.models.org_users import OrgUser
from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.schemas.org_users import OrgUserCreate, OrgUserUpdate


async def get_org_user_by_id(session: AsyncSession, org_user_id: UUID) -> OrgUser | None:
    """Get an org-user relationship by ID.

    Args:
        session (AsyncSession): The database session.
        org_user_id (UUID): The org-user relationship ID.

    Returns:
        OrgUser | None: The org-user relationship if found, None otherwise.
    """
    return await session.get(OrgUser, org_user_id)


async def get_org_user(
    session: AsyncSession, user_id: UUID, org_id: UUID
) -> OrgUser | None:
    """Get an org-user relationship by user and org.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.
        org_id (UUID): The organization ID.

    Returns:
        OrgUser | None: The org-user relationship if found, None otherwise.
    """
    result = await session.exec(
        select(OrgUser).where(
            OrgUser.user_id == user_id,
            OrgUser.org_id == org_id,
        )
    )
    return result.first()


async def get_org_users(
    session: AsyncSession,
    org_id: UUID,
    offset: int,
    limit: int,
) -> tuple[Sequence[OrgUser], int]:
    """Get a paginated list of org members.

    Args:
        session (AsyncSession): The database session.
        org_id (UUID): The organization ID.
        offset (int): The number of members to skip.
        limit (int): The maximum number of members to return.

    Returns:
        tuple[Sequence[OrgUser], int]: A tuple containing the list of members and the total count.
    """
    total_result = await session.exec(
        select(func.count()).select_from(OrgUser).where(OrgUser.org_id == org_id)
    )
    org_users_result = await session.exec(
        select(OrgUser).where(OrgUser.org_id == org_id).offset(offset).limit(limit)
    )
    return org_users_result.all(), total_result.one()


async def count_org_owners(session: AsyncSession, org_id: UUID) -> int:
    """Count owners in an organization for last-owner protection.

    Args:
        session (AsyncSession): The database session.
        org_id (UUID): The organization ID.

    Returns:
        int: The number of owners in the organization.
    """
    result = await session.exec(
        select(func.count())
        .select_from(OrgUser)
        .join(Role, OrgUser.role_id == Role.id)
        .where(OrgUser.org_id == org_id)
        .where(Role.access_level == 0)
    )
    return result.one()


async def create_org_user(
    session: AsyncSession, org_user_in: OrgUserCreate, user_id: UUID
) -> OrgUser:
    """Create a new org-user relationship.

    Args:
        session (AsyncSession): The database session.
        org_user_in (OrgUserCreate): The org-user data.
        user_id (UUID): The ID of the user creating the relationship.

    Returns:
        OrgUser: The created org-user relationship.
    """
    org_user = OrgUser(
        user_id=org_user_in.user_id,
        org_id=org_user_in.org_id,
        role_id=org_user_in.role_id,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(org_user)
    return org_user


async def update_org_user(
    session: AsyncSession, org_user: OrgUser, org_user_in: OrgUserUpdate, user_id: UUID
) -> OrgUser:
    """Update an org-user relationship.

    Args:
        session (AsyncSession): The database session.
        org_user (OrgUser): The org-user relationship to update.
        org_user_in (OrgUserUpdate): The update data.
        user_id (UUID): The ID of the user updating the relationship.

    Returns:
        OrgUser: The updated org-user relationship.
    """
    data = org_user_in.model_dump(exclude_unset=True)
    org_user.sqlmodel_update(data)
    org_user.updated_by = user_id
    session.add(org_user)
    return org_user


async def delete_org_user(session: AsyncSession, org_user: OrgUser) -> None:
    """Delete an org-user relationship.

    Args:
        session (AsyncSession): The database session.
        org_user (OrgUser): The org-user relationship to delete.
    """
    await session.delete(org_user)
