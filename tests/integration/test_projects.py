"""Integration tests for the /orgs projects router and the /projects user router."""

import uuid

import pytest
from httpx import AsyncClient

from ai_shop_helper_backend.models.project_types import ProjectType


@pytest.fixture(autouse=True)
def _roles(seeded_roles: object) -> None:
    """Ensure base roles exist for every project test (org creation needs Owner)."""


async def _create_org(client: AsyncClient, headers: dict[str, str]) -> str:
    """Create an org as the caller and return its id."""
    response = await client.post("/orgs/", headers=headers, json={"name": "Acme"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestCreateProject:
    """Tests for POST /orgs/{org_id}/projects."""

    async def test_creates_project(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """An org admin creates a project against an existing project type."""
        org_id = await _create_org(client, auth_headers)

        response = await client.post(
            f"/orgs/{org_id}/projects",
            headers=auth_headers,
            json={
                "org_id": org_id,
                "name": "Blog",
                "project_type_id": str(project_type.id),
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name"] == "Blog"
        assert data["org_id"] == org_id
        assert data["project_type_id"] == str(project_type.id)

    async def test_rejects_org_id_mismatch(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """A body org_id that differs from the path is rejected."""
        org_id = await _create_org(client, auth_headers)

        response = await client.post(
            f"/orgs/{org_id}/projects",
            headers=auth_headers,
            json={
                "org_id": str(uuid.uuid4()),
                "name": "Blog",
                "project_type_id": str(project_type.id),
            },
        )

        assert response.status_code == 400

    async def test_unknown_project_type_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Creating a project with a non-existent project type returns 404."""
        org_id = await _create_org(client, auth_headers)

        response = await client.post(
            f"/orgs/{org_id}/projects",
            headers=auth_headers,
            json={
                "org_id": org_id,
                "name": "Blog",
                "project_type_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404

    async def test_duplicate_name_conflict(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """Two projects with the same name in one org conflict."""
        org_id = await _create_org(client, auth_headers)
        body = {
            "org_id": org_id,
            "name": "Blog",
            "project_type_id": str(project_type.id),
        }
        await client.post(f"/orgs/{org_id}/projects", headers=auth_headers, json=body)

        response = await client.post(
            f"/orgs/{org_id}/projects", headers=auth_headers, json=body
        )

        assert response.status_code == 409

    async def test_requires_auth(self, client: AsyncClient, project_type: ProjectType):
        """Creating a project without auth is rejected."""
        org_id = str(uuid.uuid4())
        response = await client.post(
            f"/orgs/{org_id}/projects",
            json={
                "org_id": org_id,
                "name": "Blog",
                "project_type_id": str(project_type.id),
            },
        )
        assert response.status_code == 401

    async def test_non_admin_forbidden(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        superuser_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """A non-member cannot create a project in someone else's org."""
        org_id = await _create_org(client, auth_headers)

        response = await client.post(
            f"/orgs/{org_id}/projects",
            headers=superuser_headers,
            json={
                "org_id": org_id,
                "name": "Blog",
                "project_type_id": str(project_type.id),
            },
        )

        assert response.status_code == 403


class TestListOrgProjects:
    """Tests for GET /orgs/{org_id}/projects."""

    async def test_lists_org_projects(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """The list returns the projects created in the org."""
        org_id = await _create_org(client, auth_headers)
        await client.post(
            f"/orgs/{org_id}/projects",
            headers=auth_headers,
            json={
                "org_id": org_id,
                "name": "Blog",
                "project_type_id": str(project_type.id),
            },
        )

        response = await client.get(f"/orgs/{org_id}/projects", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Blog"


class TestGetProject:
    """Tests for GET /orgs/{org_id}/projects/{project_id}."""

    async def test_get_project(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """A member can read a project by id."""
        org_id = await _create_org(client, auth_headers)
        created = await client.post(
            f"/orgs/{org_id}/projects",
            headers=auth_headers,
            json={
                "org_id": org_id,
                "name": "Blog",
                "project_type_id": str(project_type.id),
            },
        )
        project_id = created.json()["id"]

        response = await client.get(
            f"/orgs/{org_id}/projects/{project_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["id"] == project_id

    async def test_unknown_project_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Reading a project that does not exist returns 404."""
        org_id = await _create_org(client, auth_headers)

        response = await client.get(
            f"/orgs/{org_id}/projects/{uuid.uuid4()}", headers=auth_headers
        )

        assert response.status_code == 404


class TestUpdateProject:
    """Tests for PATCH /orgs/{org_id}/projects/{project_id}."""

    async def test_updates_name(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """An admin renames a project."""
        org_id = await _create_org(client, auth_headers)
        created = await client.post(
            f"/orgs/{org_id}/projects",
            headers=auth_headers,
            json={
                "org_id": org_id,
                "name": "Blog",
                "project_type_id": str(project_type.id),
            },
        )
        project_id = created.json()["id"]

        response = await client.patch(
            f"/orgs/{org_id}/projects/{project_id}",
            headers=auth_headers,
            json={"name": "Renamed"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"


class TestDeleteProject:
    """Tests for DELETE /orgs/{org_id}/projects/{project_id}."""

    async def test_deletes_project(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """An admin deletes a project and it is then gone."""
        org_id = await _create_org(client, auth_headers)
        created = await client.post(
            f"/orgs/{org_id}/projects",
            headers=auth_headers,
            json={
                "org_id": org_id,
                "name": "Blog",
                "project_type_id": str(project_type.id),
            },
        )
        project_id = created.json()["id"]

        response = await client.delete(
            f"/orgs/{org_id}/projects/{project_id}", headers=auth_headers
        )

        assert response.status_code == 204

        follow_up = await client.get(
            f"/orgs/{org_id}/projects/{project_id}", headers=auth_headers
        )
        assert follow_up.status_code == 404


class TestUserProjects:
    """Tests for GET /projects/ (the current user's projects)."""

    async def test_lists_own_projects(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """The flat list returns projects the caller can access."""
        org_id = await _create_org(client, auth_headers)
        await client.post(
            f"/orgs/{org_id}/projects",
            headers=auth_headers,
            json={
                "org_id": org_id,
                "name": "Blog",
                "project_type_id": str(project_type.id),
            },
        )

        response = await client.get("/projects/", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Blog"

    async def test_requires_auth(self, client: AsyncClient):
        """Listing user projects without auth is rejected."""
        response = await client.get("/projects/")
        assert response.status_code == 401
