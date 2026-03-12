from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.deps import (
    CurrentOrgAdmin,
    CurrentOrgMember,
    CurrentOrgOwner,
    CurrentUser,
    PaginationDep,
    SessionDep,
)
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.schemas.orgs import OrgCreate, OrgPublic, OrgUpdate
from ai_shop_helper_backend.services import orgs

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.post("/", response_model=OrgPublic, status_code=status.HTTP_201_CREATED)
async def create_org(
    org_in: OrgCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> OrgPublic:
    """Create a new organization. Creator becomes owner.

    Args:
        org_in (OrgCreate): The organization data.
        current_user (User): The current authenticated user.
        session (SessionDep): The database session.

    Returns:
        OrgPublic: The created organization.

    Raises:
        HTTPException: 409 if the organization name is already registered.
    """
    if await orgs.get_org_by_name(session, org_in.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization name already registered",
        )
    org = await orgs.create_org_with_owner(session, org_in, current_user.id)
    return OrgPublic.model_validate(org)


@router.get("/", response_model=PaginatedResponse[OrgPublic])
async def get_my_orgs(
    current_user: CurrentUser,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[OrgPublic]:
    """Get organizations the current user is a member of.

    Args:
        current_user (User): The current authenticated user.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.

    Returns:
        PaginatedResponse[OrgPublic]: The paginated list of organizations.
    """
    items, total = await orgs.get_user_orgs(
        session, current_user.id, pagination.offset, pagination.limit
    )
    return PaginatedResponse(
        items=[OrgPublic.model_validate(org) for org in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{org_id}", response_model=OrgPublic)
async def get_org(
    org_id: UUID,
    org_member: CurrentOrgMember,
    session: SessionDep,
) -> OrgPublic:
    """Get an organization by ID. Member access only.

    Args:
        org_id (UUID): The organization ID.
        org_member (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Returns:
        OrgPublic: The organization.

    Raises:
        HTTPException: 404 if the organization does not exist.
    """
    org = await orgs.get_org_by_id(session, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return OrgPublic.model_validate(org)


@router.patch("/{org_id}", response_model=OrgPublic)
async def update_org(
    org_id: UUID,
    org_in: OrgUpdate,
    org_admin: CurrentOrgAdmin,
    session: SessionDep,
) -> OrgPublic:
    """Update an organization. Admin+ only.

    Args:
        org_id (UUID): The organization ID.
        org_in (OrgUpdate): The update data.
        org_admin (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Returns:
        OrgPublic: The updated organization.

    Raises:
        HTTPException: 404 if the organization does not exist.
        HTTPException: 409 if the organization name is already registered.
    """
    org = await orgs.get_org_by_id(session, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    if org_in.name:
        await _check_name_available(session, org_in.name, org.name)
    updated_org = await orgs.update_org(session, org, org_in, org_admin[0].id)
    return OrgPublic.model_validate(updated_org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(
    org_id: UUID,
    org_owner: CurrentOrgOwner,
    session: SessionDep,
) -> None:
    """Delete an organization. Owner only.

    Args:
        org_id (UUID): The organization ID.
        org_owner (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Raises:
        HTTPException: 404 if the organization does not exist.
    """
    org = await orgs.get_org_by_id(session, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    await orgs.delete_org(session, org)


async def _check_name_available(
    session: AsyncSession, name: str, current_name: str
) -> None:
    if name != current_name and await orgs.get_org_by_name(session, name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization name already registered",
        )
