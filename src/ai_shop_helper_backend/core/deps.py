from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.db import get_session
from ai_shop_helper_backend.core.security import decode_access_token
from ai_shop_helper_backend.models.org_users import OrgUser
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.services import users

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    refreshUrl="/auth/refresh",
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get the current authenticated user from the JWT token.

    Args:
        token (str): The JWT access token extracted from the Authorization header.
        session (AsyncSession): The database session.

    Returns:
        User: The authenticated user.

    Raises:
        HTTPException: 401 if the token is invalid or the user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if not user_id:
        raise credentials_exception
    try:
        user = await users.get_user_by_id(session, UUID(user_id))
    except ValueError:
        raise credentials_exception
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current authenticated superuser.

    Args:
        current_user (User): The current authenticated and active user.

    Returns:
        User: The authenticated superuser.

    Raises:
        HTTPException: 403 if the user is not a superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def get_current_org_member(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[User, OrgUser]:
    """Get the current user's org membership.

    Args:
        org_id (UUID): The organization ID from the path parameter.
        current_user (User): The current authenticated user.
        session (AsyncSession): The database session.

    Returns:
        tuple[User, OrgUser]: The user and their org membership.

    Raises:
        HTTPException: 403 if the user is not a member of the organization.
    """
    from ai_shop_helper_backend.services import org_users

    org_user = await org_users.get_org_user(session, current_user.id, org_id)
    if not org_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    return current_user, org_user


async def get_current_org_admin(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[User, OrgUser]:
    """Get the current user's org membership, verifying admin+ access.

    Args:
        org_id (UUID): The organization ID from the path parameter.
        current_user (User): The current authenticated user.
        session (AsyncSession): The database session.

    Returns:
        tuple[User, OrgUser]: The user and their org membership.

    Raises:
        HTTPException: 403 if the user is not a member or lacks admin permissions.
    """
    from ai_shop_helper_backend.services import org_users, roles

    org_user = await org_users.get_org_user(session, current_user.id, org_id)
    if not org_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    role = await roles.get_role_by_id(session, org_user.role_id)
    if not role or role.access_level > 10:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user, org_user


async def get_current_org_owner(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[User, OrgUser]:
    """Get the current user's org membership, verifying owner access.

    Args:
        org_id (UUID): The organization ID from the path parameter.
        current_user (User): The current authenticated user.
        session (AsyncSession): The database session.

    Returns:
        tuple[User, OrgUser]: The user and their org membership.

    Raises:
        HTTPException: 403 if the user is not the owner of the organization.
    """
    from ai_shop_helper_backend.services import org_users, roles

    org_user = await org_users.get_org_user(session, current_user.id, org_id)
    if not org_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    role = await roles.get_role_by_id(session, org_user.role_id)
    if not role or role.access_level != 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required",
        )
    return current_user, org_user


class PaginationParams:
    """Pagination parameters for list endpoints."""

    def __init__(
        self,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> None:
        """Initialize the pagination parameters.

        Args:
            offset (int): The number of items to skip before starting to collect the result set. Default is 0.
            limit (int): The maximum number of items to return. Default is 50, maximum is 100.
        """
        self.offset = offset
        self.limit = limit


SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSuperUser = Annotated[User, Depends(get_current_superuser)]
CurrentOrgMember = Annotated[tuple[User, OrgUser], Depends(get_current_org_member)]
CurrentOrgAdmin = Annotated[tuple[User, OrgUser], Depends(get_current_org_admin)]
CurrentOrgOwner = Annotated[tuple[User, OrgUser], Depends(get_current_org_owner)]
PaginationDep = Annotated[PaginationParams, Depends()]
