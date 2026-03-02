from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from ai_shop_helper_backend.core.deps import (
    CurrentSuperUser,
    CurrentUser,
    PaginationDep,
    SessionDep,
)
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.schemas.users import UserAdminUpdate, UserPublic, UserUpdate
from ai_shop_helper_backend.services import users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: CurrentUser) -> UserPublic:
    """Get the current authenticated user.

    Args:
        current_user (User): The current authenticated user.

    Returns:
        UserPublic: The current user.
    """
    return UserPublic.model_validate(current_user)


@router.patch("/me", response_model=UserPublic)
async def update_me(
    user_in: UserUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> UserPublic:
    """Update the current authenticated user.

    Args:
        user_in (UserUpdate): The update data.
        current_user (User): The current authenticated user.
        session (SessionDep): The database session.

    Returns:
        UserPublic: The updated user.

    Raises:
        HTTPException: 409 if the email is already registered.
    """
    if user_in.email and user_in.email != current_user.email:
        if await users.get_user_by_email(session, user_in.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
    return UserPublic.model_validate(
        await users.update_user(session, current_user, user_in)
    )


@router.get("/", response_model=PaginatedResponse[UserPublic])
async def get_users(
    current_superuser: CurrentSuperUser,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[UserPublic]:
    """Get a paginated list of users. Superuser only.

    Args:
        current_superuser (User): The current superuser.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.

    Returns:
        PaginatedResponse[UserPublic]: The paginated list of users.
    """
    items, total = await users.get_users(session, pagination.offset, pagination.limit)
    return PaginatedResponse(
        items=[UserPublic.model_validate(u) for u in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: UUID,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> UserPublic:
    """Get a user by ID. Superuser only.

    Args:
        user_id (UUID): The user ID.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        UserPublic: The user.

    Raises:
        HTTPException: 404 if the user does not exist.
    """
    user = await users.get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserPublic.model_validate(user)


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: UUID,
    user_in: UserAdminUpdate,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> UserPublic:
    """Update a user. Superuser only.

    Args:
        user_id (UUID): The user ID.
        user_in (UserAdminUpdate): The update data.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Returns:
        UserPublic: The updated user.

    Raises:
        HTTPException: 404 if the user does not exist.
        HTTPException: 409 if the email is already registered.
    """
    user = await users.get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user_in.email and user_in.email != user.email:
        if await users.get_user_by_email(session, user_in.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
    return UserPublic.model_validate(await users.update_user(session, user, user_in))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_superuser: CurrentSuperUser,
    session: SessionDep,
) -> None:
    """Delete a user. Superuser only.

    Args:
        user_id (UUID): The user ID.
        current_superuser (User): The current superuser.
        session (SessionDep): The database session.

    Raises:
        HTTPException: 400 if the superuser tries to delete itself.
        HTTPException: 404 if the user does not exist.
    """
    if user_id == current_superuser.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Superusers cannot delete themselves",
        )
    user = await users.get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await users.delete_user(session, user)
