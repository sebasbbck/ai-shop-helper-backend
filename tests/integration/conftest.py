from collections.abc import AsyncGenerator, Callable, Coroutine, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from testcontainers.postgres import PostgresContainer

from ai_shop_helper_backend.core.db import AsyncSessionLocal, get_session
from ai_shop_helper_backend.main import app
from ai_shop_helper_backend.models.project_types import ProjectType
from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.models.users import User


@pytest.fixture(scope="session", autouse=True)
def engine() -> Generator[AsyncEngine]:
    """Start a PostgreSQL container for the entire test session.

    Creates all SQLModel tables via a synchronous engine, then yields a shared async
    engine for the rest of the suite.

    Yields:
        AsyncEngine: An async SQLAlchemy engine connected to the test database.
    """
    with PostgresContainer("postgres:17", driver="psycopg") as container:
        url = container.get_connection_url()
        engine = create_engine(url)
        SQLModel.metadata.create_all(engine)
        engine.dispose()
        async_engine = create_async_engine(url, echo=False)
        yield async_engine


@pytest.fixture
async def session(
    engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async SQLAlchemy session for tests, using the shared engine fixture.

    Yields:
        AsyncSession: An asynchronous database session connected to the test database.
    """
    kw = AsyncSessionLocal.kw.copy()
    kw["bind"] = engine
    kw["class_"] = AsyncSession
    session_maker = async_sessionmaker(**kw)
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(autouse=True)
async def clean_db(engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """Truncate all tables after each test to ensure isolation."""
    yield
    async with engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def client(
    session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP client for testing FastAPI endpoints, with DB session override.

    Yields:
        AsyncClient: An HTTP client for testing FastAPI endpoints.
    """

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def create_user(
    session: AsyncSession, make_user: Callable[..., User]
) -> Callable[..., Coroutine[None, None, User]]:
    """Return an async factory that commits a User to the test DB.

    Each call opens its own session so the user is immediately visible to
    subsequent requests through the client.

    Examples:
        user = await make_user()
        superuser = await make_user(is_superuser=True, email="admin@example.com")

    Returns:
        Callable[..., Coroutine[Any, Any, User]]: An async factory function that creates
            and commits
    """

    async def factory(**kwargs: object) -> User:
        user = make_user(**kwargs)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    return factory


@pytest.fixture
async def auth_headers(
    client: AsyncClient, create_user: Callable[..., Coroutine[None, None, User]]
) -> dict[str, str]:
    """Create a regular user and return Bearer auth headers for ."""
    user = await create_user()
    response = await client.post(
        "/auth/login",
        data={"username": user.email, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def superuser_headers(
    client: AsyncClient, create_user: Callable[..., Coroutine[None, None, User]]
) -> dict[str, str]:
    """Create a superuser and return Bearer auth headers for them."""
    user = await create_user(email="admin@example.com", is_superuser=True)
    response = await client.post(
        "/auth/login",
        data={"username": user.email, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def seed_author(
    create_user: Callable[..., Coroutine[None, None, User]],
) -> User:
    """A user to author base seed rows (roles, project types) in tests."""
    return await create_user(email="seed-author@example.com")


@pytest.fixture
async def seeded_roles(session: AsyncSession, seed_author: User) -> dict[str, Role]:
    """Insert the base Owner/Admin/Member roles (wiped by clean_db otherwise)."""
    roles = {
        name: Role(
            name=name,
            access_level=level,
            created_by=seed_author.id,
            updated_by=seed_author.id,
        )
        for name, level in (("Owner", 0), ("Admin", 10), ("Member", 20))
    }
    for role in roles.values():
        session.add(role)
    await session.commit()
    for role in roles.values():
        await session.refresh(role)
    return roles


@pytest.fixture
async def project_type(session: AsyncSession, seed_author: User) -> ProjectType:
    """Insert a base project type for project tests."""
    pt = ProjectType(
        name="WordPress",
        created_by=seed_author.id,
        updated_by=seed_author.id,
    )
    session.add(pt)
    await session.commit()
    await session.refresh(pt)
    return pt
