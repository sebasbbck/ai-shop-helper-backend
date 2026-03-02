from collections.abc import Sequence
from uuid import UUID

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.security import hash_password, verify_password
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.schemas.users import UserAdminUpdate, UserCreate, UserUpdate


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    """Get a user by ID.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.

    Returns:
        User | None: The user if found, None otherwise.
    """
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Get a user by email.

    Args:
        session (AsyncSession): The database session.
        email (str): The user email.

    Returns:
        User | None: The user if found, None otherwise.
    """
    result = await session.exec(select(User).where(User.email == email))
    return result.first()


async def get_users(
    session: AsyncSession,
    offset: int,
    limit: int,
) -> tuple[Sequence[User], int]:
    """Get a paginated list of users.

    Args:
        session (AsyncSession): The database session.
        offset (int): The number of users to skip.
        limit (int): The maximum number of users to return.

    Returns:
        tuple[Sequence[User], int]: A tuple containing the list of users and the total count of users.
    """
    total_result = await session.exec(select(func.count()).select_from(User))
    total = total_result.one()
    users_result = await session.exec(select(User).offset(offset).limit(limit))
    return users_result.all(), total


async def create_user(session: AsyncSession, user_in: UserCreate) -> User:
    """Create a new user.

    Args:
        session (AsyncSession): The database session.
        user_in (UserCreate): The user data.

    Returns:
        User: The created user.
    """
    user = User(
        email=user_in.email,
        name=user_in.name,
        hashed_password=hash_password(user_in.password),
    )
    session.add(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    """Authenticate a user by email and password.

    Args:
        session (AsyncSession): The database session.
        email (str): The user email.
        password (str): The plain password.

    Returns:
        User | None: The user if authenticated, None otherwise.
    """
    user = await get_user_by_email(session, email)
    if (
        not user
        or not verify_password(password, user.hashed_password)
        or not user.is_active
    ):
        return None
    return user


async def update_user(
    session: AsyncSession, user: User, user_in: UserUpdate | UserAdminUpdate
) -> User:
    """Update a user.

    Args:
        session (AsyncSession): The database session.
        user (User): The user to update.
        user_in (UserUpdate | UserAdminUpdate): The update data.

    Returns:
        User: The updated user.
    """
    data = user_in.model_dump(exclude_unset=True)
    if password := data.pop("password", None):
        data["hashed_password"] = hash_password(password)
    user.sqlmodel_update(data)
    session.add(user)
    return user


async def delete_user(session: AsyncSession, user: User) -> None:
    """Delete a user.

    Args:
        session (AsyncSession): The database session.
        user (User): The user to delete.
    """
    await session.delete(user)
