"""Integration tests for the /roles router (superuser only)."""

import uuid

from httpx import AsyncClient


async def _create_role(
    client: AsyncClient,
    headers: dict[str, str],
    name: str = "Editor",
    access_level: int = 30,
) -> str:
    """Create a role as a superuser and return its id."""
    response = await client.post(
        "/roles/",
        headers=headers,
        json={"name": name, "access_level": access_level},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestCreateRole:
    """Tests for POST /roles/."""

    async def test_creates_role(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A superuser creates a role with a description and access level."""
        response = await client.post(
            "/roles/",
            headers=superuser_headers,
            json={
                "name": "Editor",
                "description": "Can edit content",
                "access_level": 30,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name"] == "Editor"
        assert data["access_level"] == 30
        assert data["description"] == "Can edit content"

    async def test_duplicate_name_conflict(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Two roles with the same name conflict."""
        await _create_role(client, superuser_headers)

        response = await client.post(
            "/roles/",
            headers=superuser_headers,
            json={"name": "Editor", "access_level": 40},
        )

        assert response.status_code == 409

    async def test_rejects_out_of_range_access_level(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """An access level above 100 fails validation."""
        response = await client.post(
            "/roles/",
            headers=superuser_headers,
            json={"name": "Editor", "access_level": 500},
        )

        assert response.status_code == 422

    async def test_requires_auth(self, client: AsyncClient):
        """Creating a role without auth is rejected."""
        response = await client.post(
            "/roles/", json={"name": "Editor", "access_level": 30}
        )
        assert response.status_code == 401

    async def test_regular_user_forbidden(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """A regular user cannot create a role."""
        response = await client.post(
            "/roles/",
            headers=auth_headers,
            json={"name": "Editor", "access_level": 30},
        )
        assert response.status_code == 403


class TestListAndGetRoles:
    """Tests for GET /roles/ and /{id}."""

    async def test_lists_roles(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """The list returns created roles."""
        await _create_role(client, superuser_headers)

        response = await client.get("/roles/", headers=superuser_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_get_role(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A role is readable by id."""
        role_id = await _create_role(client, superuser_headers)

        response = await client.get(f"/roles/{role_id}", headers=superuser_headers)

        assert response.status_code == 200
        assert response.json()["id"] == role_id

    async def test_get_unknown_not_found(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Reading a non-existent role returns 404."""
        response = await client.get(f"/roles/{uuid.uuid4()}", headers=superuser_headers)
        assert response.status_code == 404


class TestUpdateRole:
    """Tests for PATCH /roles/{id}."""

    async def test_updates_role(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A superuser updates a role's access level."""
        role_id = await _create_role(client, superuser_headers)

        response = await client.patch(
            f"/roles/{role_id}",
            headers=superuser_headers,
            json={"access_level": 50},
        )

        assert response.status_code == 200
        assert response.json()["access_level"] == 50


class TestDeleteRole:
    """Tests for DELETE /roles/{id}."""

    async def test_deletes_role(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A superuser deletes a role and it is then gone."""
        role_id = await _create_role(client, superuser_headers)

        response = await client.delete(f"/roles/{role_id}", headers=superuser_headers)

        assert response.status_code == 204

        follow_up = await client.get(f"/roles/{role_id}", headers=superuser_headers)
        assert follow_up.status_code == 404
