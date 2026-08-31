from collections.abc import Sequence
from uuid import UUID

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.models.org_users import OrgUser
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.schemas.orgs import OrgCreate, OrgUpdate


async def get_org_by_id(session: AsyncSession, org_id: UUID) -> Org | None:
    """Get an organization by ID.

    Args:
        session (AsyncSession): The database session.
        org_id (UUID): The organization ID.

    Returns:
        Org | None: The organization if found, None otherwise.
    """
    return await session.get(Org, org_id)


async def get_org_by_name(session: AsyncSession, name: str) -> Org | None:
    """Get an organization by name.

    Args:
        session (AsyncSession): The database session.
        name (str): The organization name.

    Returns:
        Org | None: The organization if found, None otherwise.
    """
    result = await session.exec(select(Org).where(Org.name == name))
    return result.first()


async def get_user_orgs(
    session: AsyncSession,
    user_id: UUID,
    offset: int,
    limit: int,
) -> tuple[Sequence[Org], int]:
    """Get organizations the user is a member of.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.
        offset (int): The number of organizations to skip.
        limit (int): The maximum number of organizations to return.

    Returns:
        tuple[Sequence[Org], int]: A tuple containing the list of organizations and the total count.
    """
    total_result = await session.exec(
        select(func.count())
        .select_from(Org)
        .join(OrgUser, col(Org.id) == col(OrgUser.org_id))
        .where(OrgUser.user_id == user_id)
    )

    orgs_result = await session.exec(
        select(Org)
        .join(OrgUser, col(Org.id) == col(OrgUser.org_id))
        .where(OrgUser.user_id == user_id)
        .offset(offset)
        .limit(limit)
    )

    return orgs_result.all(), total_result.one()


async def create_org_with_owner(
    session: AsyncSession, org_in: OrgCreate, user_id: UUID
) -> Org:
    """Create an organization and assign creator as owner.

    Args:
        session (AsyncSession): The database session.
        org_in (OrgCreate): The organization data.
        user_id (UUID): The ID of the user creating the organization.

    Returns:
        Org: The created organization.
    """
    from ai_shop_helper_backend.schemas.org_users import OrgUserCreate
    from ai_shop_helper_backend.services import org_users, roles

    org = Org(
        name=org_in.name,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(org)
    await session.flush()

    owner_role = await roles.get_role_by_access_level(session, 0)
    if owner_role is None:
        raise ValueError("Owner role (access_level=0) not found")

    org_user_in = OrgUserCreate(
        user_id=user_id,
        org_id=org.id,
        role_id=owner_role.id,
    )
    await org_users.create_org_user(session, org_user_in, user_id)

    from ai_shop_helper_backend.core.constants import FREE_TIER_CREDITS
    from ai_shop_helper_backend.services import billing, referrals

    await billing.grant_purchased(
        session, org, FREE_TIER_CREDITS, reason="signup_bonus", meta={"free": True}
    )
    await referrals.link_referee_org(session, user_id, org.id)

    return org


async def update_org(
    session: AsyncSession, org: Org, org_in: OrgUpdate, user_id: UUID
) -> Org:
    """Update an organization.

    Args:
        session (AsyncSession): The database session.
        org (Org): The organization to update.
        org_in (OrgUpdate): The update data.
        user_id (UUID): The ID of the user updating the organization.

    Returns:
        Org: The updated organization.
    """
    data = org_in.model_dump(exclude_unset=True)
    org.sqlmodel_update(data)
    org.updated_by = user_id
    session.add(org)
    return org


async def delete_org(session: AsyncSession, org: Org) -> None:
    """Delete an organization.

    Args:
        session (AsyncSession): The database session.
        org (Org): The organization to delete.
    """
    await session.delete(org)


async def get_user_orgs_with_projects(
    session: AsyncSession, user_id: UUID, offset: int, limit: int
) -> tuple[list[tuple[Org, list[Project]]], int]:
    """Get organizations the user is a member of with their projects.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.
        offset (int): The number of organizations to skip.
        limit (int): The maximum number of organizations to return.

    Returns:
        tuple[list[tuple[Org, list[Project]]], int]: A tuple containing the list of
            organizations with their projects and the total count of organizations.
    """
    total_result = await session.exec(
        select(func.count())
        .select_from(Org)
        .join(OrgUser, col(Org.id) == col(OrgUser.org_id))
        .where(OrgUser.user_id == user_id)
    )
    total = total_result.one()

    orgs_result = await session.exec(
        select(Org)
        .join(OrgUser, col(Org.id) == col(OrgUser.org_id))
        .where(OrgUser.user_id == user_id)
        .offset(offset)
        .limit(limit)
    )
    orgs = orgs_result.all()

    org_ids = [org.id for org in orgs]
    if org_ids:
        projects_result = await session.exec(
            select(Project).where(col(Project.org_id).in_(org_ids))
        )
        all_projects = projects_result.all()
    else:
        all_projects = []

    projects_by_org: dict[UUID, list[Project]] = {org.id: [] for org in orgs}
    for project in all_projects:
        projects_by_org[project.org_id].append(project)

    return [(org, projects_by_org[org.id]) for org in orgs], total
