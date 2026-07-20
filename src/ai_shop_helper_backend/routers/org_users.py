from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from ai_shop_helper_backend.core.deps import (
    CurrentOrgAdmin,
    CurrentOrgMember,
    PaginationDep,
    SessionDep,
)
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.schemas.org_users import (
    OrgUserCreate,
    OrgUserPublic,
    OrgUserUpdate,
)
from ai_shop_helper_backend.services import org_users, roles, users

router = APIRouter(prefix="/orgs", tags=["org-members"])


@router.post(
    "/{org_id}/members",
    response_model=OrgUserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def add_org_member(
    org_id: UUID,
    org_user_in: OrgUserCreate,
    org_admin: CurrentOrgAdmin,
    session: SessionDep,
) -> OrgUserPublic:
    """Add a member to the organization. Admin+ only.

    Args:
        org_id (UUID): The organization ID.
        org_user_in (OrgUserCreate): The member data.
        org_admin (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Returns:
        OrgUserPublic: The created org membership.

    Raises:
        HTTPException: 400 if org_id mismatch.
        HTTPException: 404 if user or role does not exist.
        HTTPException: 409 if the user is already a member.
    """
    if org_user_in.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization ID mismatch",
        )

    user = await users.get_user_by_id(session, org_user_in.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    role = await roles.get_role_by_id(session, org_user_in.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    existing = await org_users.get_org_user(session, org_user_in.user_id, org_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organization",
        )

    org_user = await org_users.create_org_user(session, org_user_in, org_admin[0].id)
    return OrgUserPublic.model_validate(org_user)


@router.get("/{org_id}/members", response_model=PaginatedResponse[OrgUserPublic])
async def get_org_members(
    org_id: UUID,
    org_member: CurrentOrgMember,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[OrgUserPublic]:
    """List organization members. Member access.

    Args:
        org_id (UUID): The organization ID.
        org_member (tuple[User, OrgUser]): The current user and their org membership.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.

    Returns:
        PaginatedResponse[OrgUserPublic]: The paginated list of members.
    """
    items, total = await org_users.get_org_users(
        session, org_id, pagination.offset, pagination.limit
    )
    return PaginatedResponse(
        items=[OrgUserPublic.model_validate(ou) for ou in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{org_id}/members/{user_id}", response_model=OrgUserPublic)
async def get_org_member(
    org_id: UUID,
    user_id: UUID,
    org_member: CurrentOrgMember,
    session: SessionDep,
) -> OrgUserPublic:
    """Get specific member details. Member access.

    Args:
        org_id (UUID): The organization ID.
        user_id (UUID): The user ID.
        org_member (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Returns:
        OrgUserPublic: The org membership.

    Raises:
        HTTPException: 404 if the member is not found.
    """
    org_user = await org_users.get_org_user(session, user_id, org_id)
    if not org_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    return OrgUserPublic.model_validate(org_user)


@router.patch("/{org_id}/members/{user_id}", response_model=OrgUserPublic)
async def update_org_member_role(
    org_id: UUID,
    user_id: UUID,
    org_user_in: OrgUserUpdate,
    org_admin: CurrentOrgAdmin,
    session: SessionDep,
) -> OrgUserPublic:
    """Update member's role. Admin+ only.

    Args:
        org_id (UUID): The organization ID.
        user_id (UUID): The user ID.
        org_user_in (OrgUserUpdate): The update data.
        org_admin (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Returns:
        OrgUserPublic: The updated org membership.

    Raises:
        HTTPException: 404 if the member or role does not exist.
        HTTPException: 400 if removing last owner.
    """
    org_user = await org_users.get_org_user(session, user_id, org_id)
    if not org_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    new_role = await roles.get_role_by_id(session, org_user_in.role_id)
    if not new_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    old_role = await roles.get_role_by_id(session, org_user.role_id)
    if old_role and old_role.access_level == 0 and new_role.access_level != 0:
        owner_count = await org_users.count_org_owners(session, org_id)
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove last owner. Transfer ownership first.",
            )

    updated_org_user = await org_users.update_org_user(
        session, org_user, org_user_in, org_admin[0].id
    )
    return OrgUserPublic.model_validate(updated_org_user)


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_org_member(
    org_id: UUID,
    user_id: UUID,
    org_admin: CurrentOrgAdmin,
    session: SessionDep,
) -> None:
    """Remove member from organization. Admin+ only. Last-owner protection applies.

    Args:
        org_id (UUID): The organization ID.
        user_id (UUID): The user ID.
        org_admin (tuple[User, OrgUser]): The current user and their org membership.
        session (SessionDep): The database session.

    Raises:
        HTTPException: 404 if the member does not exist.
        HTTPException: 400 if removing last owner.
    """
    org_user = await org_users.get_org_user(session, user_id, org_id)
    if not org_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    role = await roles.get_role_by_id(session, org_user.role_id)
    if role and role.access_level == 0:
        owner_count = await org_users.count_org_owners(session, org_id)
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove last owner. Transfer ownership first.",
            )

    await org_users.delete_org_user(session, org_user)
