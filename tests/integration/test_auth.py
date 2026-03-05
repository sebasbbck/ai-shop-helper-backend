"""Integration tests for the /auth router."""

from collections.abc import Callable, Coroutine

from httpx import AsyncClient

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.models.users import User


class TestRegister:
    """Tests for the /auth/register endpoint."""

    async def test_success(self, client: AsyncClient):
        """Test successful registration."""
        response = await client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "name": "Alice",
                "password": "password123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "alice@example.com"
        assert data["name"] == "Alice"
        assert "id" in data
        assert "hashed_password" not in data

    async def test_duplicate_email(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """Test that registering with an email that already exists returns a 409 conflict."""
        await create_user(email="bob@example.com")

        response = await client.post(
            "/auth/register",
            json={
                "email": "bob@example.com",
                "name": "Bob 2",
                "password": "password123",
            },
        )

        assert response.status_code == 409

    async def test_password_too_short(self, client: AsyncClient):
        """Test that registering with a password that is too short returns a 422 validation error."""
        response = await client.post(
            "/auth/register",
            json={"email": "short@example.com", "name": "Short", "password": "short"},
        )
        assert response.status_code == 422


class TestLogin:
    """Tests for the /auth/login endpoint."""

    async def test_success(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """Test successful login returns access token and sets refresh token cookie."""
        await create_user(email="carol@example.com")

        response = await client.post(
            "/auth/login",
            data={"username": "carol@example.com", "password": "password123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert settings.REFRESH_TOKEN_COOKIE in response.cookies

    async def test_wrong_password(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """Test that logging in with the wrong password returns a 401 unauthorized error."""
        await create_user(email="dave@example.com")

        response = await client.post(
            "/auth/login",
            data={"username": "dave@example.com", "password": "wrongpassword"},
        )

        assert response.status_code == 401

    async def test_unknown_email(self, client: AsyncClient):
        """Test that logging in with an email that doesn't exist returns a 401 unauthorized error."""
        response = await client.post(
            "/auth/login",
            data={"username": "ghost@example.com", "password": "password123"},
        )

        assert response.status_code == 401

    async def test_inactive_user(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """Test that logging in with an inactive user returns a 401 unauthorized error."""
        await create_user(email="inactive@example.com", is_active=False)

        response = await client.post(
            "/auth/login",
            data={"username": "inactive@example.com", "password": "password123"},
        )

        assert response.status_code == 401


class TestRefresh:
    """Tests for the /auth/refresh endpoint."""

    async def test_success_and_rotates_token(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """Test that providing a valid refresh token cookie returns a new access token and rotates the refresh token."""
        await create_user(email="eve@example.com")
        login_resp = await client.post(
            "/auth/login",
            data={"username": "eve@example.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        refresh_cookie = login_resp.cookies.get(settings.REFRESH_TOKEN_COOKIE)
        assert refresh_cookie is not None

        client.cookies.set(settings.REFRESH_TOKEN_COOKIE, refresh_cookie)
        refresh_resp = await client.post("/auth/refresh")
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.json()

        # Token rotation: old cookie must now be rejected
        client.cookies.set(settings.REFRESH_TOKEN_COOKIE, refresh_cookie)
        reuse_resp = await client.post("/auth/refresh")
        assert reuse_resp.status_code == 401

    async def test_invalid_cookie(self, client: AsyncClient):
        """Test that providing an invalid refresh token cookie returns a 401 unauthorized error."""
        client.cookies.set(settings.REFRESH_TOKEN_COOKIE, "not-a-real-token")
        response = await client.post("/auth/refresh")
        assert response.status_code == 401

    async def test_missing_cookie(self, client: AsyncClient):
        """Test that not providing a refresh token cookie returns a 422 validation error."""
        response = await client.post("/auth/refresh")
        assert response.status_code == 422


class TestLogout:
    """Tests for the /auth/logout endpoint."""

    async def test_success(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """Test that logging out with a valid access token deletes the refresh token and cookie."""
        await create_user(email="frank@example.com")
        login_resp = await client.post(
            "/auth/login",
            data={"username": "frank@example.com", "password": "password123"},
        )
        access_token = login_resp.json()["access_token"]

        response = await client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

    async def test_logout_by_token_not_user(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """Test that logging out deletes the refresh token for the current token, not all tokens for the user."""
        await create_user(email="grace@example.com")
        login_resp1 = await client.post(
            "/auth/login",
            data={"username": "grace@example.com", "password": "password123"},
        )
        login_resp2 = await client.post(
            "/auth/login",
            data={"username": "grace@example.com", "password": "password123"},
        )
        token1 = login_resp1.json()["access_token"]
        refresh_cookie1 = login_resp1.cookies.get(settings.REFRESH_TOKEN_COOKIE)
        assert refresh_cookie1 is not None
        token2 = login_resp2.json()["access_token"]
        refresh_cookie2 = login_resp2.cookies.get(settings.REFRESH_TOKEN_COOKIE)
        assert refresh_cookie2 is not None

        # Logout with token1
        client.cookies.set(settings.REFRESH_TOKEN_COOKIE, refresh_cookie1)
        response = await client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert response.status_code == 204

        # token1 should now be invalid but token2 should still work
        client.cookies.set(settings.REFRESH_TOKEN_COOKIE, refresh_cookie1)
        refresh_resp1 = await client.post(
            "/auth/refresh", headers={"Authorization": f"Bearer {token1}"}
        )
        client.cookies.set(settings.REFRESH_TOKEN_COOKIE, refresh_cookie2)
        refresh_resp2 = await client.post(
            "/auth/refresh", headers={"Authorization": f"Bearer {token2}"}
        )
        assert refresh_resp1.status_code == 401
        assert refresh_resp2.status_code == 200

    async def test_requires_auth(self, client: AsyncClient):
        """Test that logging out without an access token returns a 401 unauthorized error."""
        response = await client.post("/auth/logout")
        assert response.status_code == 401
