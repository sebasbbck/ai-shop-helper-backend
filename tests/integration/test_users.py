"""Integration tests for the /users router."""

import uuid
from collections.abc import Callable, Coroutine

from httpx import AsyncClient

from ai_shop_helper_backend.models.users import User


class TestGetMe:
    """Tests for the /users/me endpoint."""

    async def test_success(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test that /users/me returns the current user's information when authenticated."""
        response = await client.get("/users/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "hashed_password" not in data

    async def test_requires_auth(self, client: AsyncClient):
        """Test that /users/me returns a 401 unauthorized error when no access token is provided."""
        response = await client.get("/users/me")

        assert response.status_code == 401


class TestUpdateMe:
    """Tests for the /users/me PATCH endpoint."""

    async def test_updates_name(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test that the user can update their name."""
        response = await client.patch(
            "/users/me",
            headers=auth_headers,
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    async def test_updates_password(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test that the user can update their password."""
        response = await client.patch(
            "/users/me",
            headers=auth_headers,
            json={"password": "newpassword99"},
        )

        assert response.status_code == 200

    async def test_email_conflict(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ):
        """Test that updating the email to one that is already taken returns a 409 conflict error."""
        await create_user(email="taken@example.com")

        response = await client.patch(
            "/users/me",
            headers=auth_headers,
            json={"email": "taken@example.com"},
        )

        assert response.status_code == 409

    async def test_password_too_short(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test that updating the password to one that is too short returns a 422 validation error."""
        response = await client.patch(
            "/users/me",
            headers=auth_headers,
            json={"password": "short"},
        )

        assert response.status_code == 422


class TestGetUsers:
    """Tests for the GET /users endpoint."""

    async def test_success(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Test that a superuser can get a paginated list of users."""
        response = await client.get("/users/", headers=superuser_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    async def test_forbidden_for_regular_user(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test that a regular user cannot access the list of users."""
        response = await client.get("/users/", headers=auth_headers)

        assert response.status_code == 403


class TestGetUserById:
    """Tests for the GET /users/{user_id} endpoint."""

    async def test_success(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
        superuser_headers: dict[str, str],
    ):
        """Test that a superuser can get a user by ID."""
        target = await create_user(email="target@example.com")

        response = await client.get(f"/users/{target.id}", headers=superuser_headers)

        assert response.status_code == 200
        assert response.json()["email"] == "target@example.com"

    async def test_not_found(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Test that getting a user by a non-existent ID returns a 404 not found error."""
        response = await client.get(f"/users/{uuid.uuid4()}", headers=superuser_headers)

        assert response.status_code == 404


class TestUpdateUserById:
    """Tests for the PATCH /users/{user_id} endpoint."""

    async def test_success(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
        superuser_headers: dict[str, str],
    ):
        """Test that a superuser can update another user's name."""
        target = await create_user(email="patchme@example.com")

        response = await client.patch(
            f"/users/{target.id}",
            headers=superuser_headers,
            json={"name": "Admin Updated"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Admin Updated"

    async def test_email_conflict(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
        superuser_headers: dict[str, str],
    ):
        """Test that updating a user's email to one that is already taken returns a 409 conflict error."""
        await create_user(email="existing@example.com")
        target = await create_user(email="target@example.com")

        response = await client.patch(
            f"/users/{target.id}",
            headers=superuser_headers,
            json={"email": "existing@example.com"},
        )

        assert response.status_code == 409

    async def test_not_found(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Test that updating a non-existent user returns a 404 not found error."""
        response = await client.patch(
            f"/users/{uuid.uuid4()}",
            headers=superuser_headers,
            json={"name": "Does Not Exist"},
        )

        assert response.status_code == 404


class TestDeleteUser:
    """Tests for the DELETE /users/{user_id} endpoint."""

    async def test_success(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
        superuser_headers: dict[str, str],
    ):
        """Test that a superuser can delete another user."""
        target = await create_user(email="deleteme@example.com")

        response = await client.delete(f"/users/{target.id}", headers=superuser_headers)

        assert response.status_code == 204

    async def test_cannot_delete_self(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Test that a superuser cannot delete their own user account."""
        me_resp = await client.get("/users/me", headers=superuser_headers)
        own_id = me_resp.json()["id"]

        response = await client.delete(f"/users/{own_id}", headers=superuser_headers)

        assert response.status_code == 400

    async def test_not_found(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Test that deleting a non-existent user returns a 404 not found error."""
        response = await client.delete(
            f"/users/{uuid.uuid4()}", headers=superuser_headers
        )

        assert response.status_code == 404
