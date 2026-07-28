"""Integration tests for the /project-types router (superuser only)."""

import uuid

from httpx import AsyncClient


async def _create_project_type(
    client: AsyncClient, headers: dict[str, str], name: str = "WordPress"
) -> str:
    """Create a project type as a superuser and return its id."""
    response = await client.post(
        "/project-types/", headers=headers, json={"name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestCreateProjectType:
    """Tests for POST /project-types/."""

    async def test_creates_project_type(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A superuser creates a project type."""
        response = await client.post(
            "/project-types/", headers=superuser_headers, json={"name": "WordPress"}
        )

        assert response.status_code == 201, response.text
        assert response.json()["name"] == "WordPress"

    async def test_duplicate_name_conflict(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Two project types with the same name conflict."""
        await _create_project_type(client, superuser_headers)

        response = await client.post(
            "/project-types/", headers=superuser_headers, json={"name": "WordPress"}
        )

        assert response.status_code == 409

    async def test_requires_auth(self, client: AsyncClient):
        """Creating a project type without auth is rejected."""
        response = await client.post("/project-types/", json={"name": "WordPress"})
        assert response.status_code == 401

    async def test_regular_user_forbidden(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """A regular user cannot create a project type."""
        response = await client.post(
            "/project-types/", headers=auth_headers, json={"name": "WordPress"}
        )
        assert response.status_code == 403


class TestListAndGetProjectTypes:
    """Tests for GET /project-types/ and /{id}."""

    async def test_lists_project_types(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """The list returns created project types (any authed user can read)."""
        await _create_project_type(client, superuser_headers)

        response = await client.get("/project-types/", headers=superuser_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_regular_user_can_read(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        auth_headers: dict[str, str],
    ):
        """A regular authenticated user can list project types."""
        await _create_project_type(client, superuser_headers)

        response = await client.get("/project-types/", headers=auth_headers)

        assert response.status_code == 200

    async def test_get_project_type(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A project type is readable by id."""
        pt_id = await _create_project_type(client, superuser_headers)

        response = await client.get(
            f"/project-types/{pt_id}", headers=superuser_headers
        )

        assert response.status_code == 200
        assert response.json()["id"] == pt_id

    async def test_get_unknown_not_found(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Reading a non-existent project type returns 404."""
        response = await client.get(
            f"/project-types/{uuid.uuid4()}", headers=superuser_headers
        )
        assert response.status_code == 404


class TestUpdateProjectType:
    """Tests for PATCH /project-types/{id}."""

    async def test_updates_name(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A superuser renames a project type."""
        pt_id = await _create_project_type(client, superuser_headers)

        response = await client.patch(
            f"/project-types/{pt_id}",
            headers=superuser_headers,
            json={"name": "Shopify"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Shopify"


class TestDeleteProjectType:
    """Tests for DELETE /project-types/{id}."""

    async def test_deletes_project_type(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A superuser deletes a project type and it is then gone."""
        pt_id = await _create_project_type(client, superuser_headers)

        response = await client.delete(
            f"/project-types/{pt_id}", headers=superuser_headers
        )

        assert response.status_code == 204

        follow_up = await client.get(
            f"/project-types/{pt_id}", headers=superuser_headers
        )
        assert follow_up.status_code == 404
