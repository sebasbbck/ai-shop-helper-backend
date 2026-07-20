"""Integration tests for the /agents router (mutations superuser only)."""

import uuid

from httpx import AsyncClient

from ai_shop_helper_backend.models.project_types import ProjectType


async def _create_agent(
    client: AsyncClient, headers: dict[str, str], name: str = "Blog Writer"
) -> str:
    """Create an agent as a superuser and return its id."""
    response = await client.post("/agents/", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestCreateAgent:
    """Tests for POST /agents/."""

    async def test_creates_agent(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A superuser creates an agent with a description."""
        response = await client.post(
            "/agents/",
            headers=superuser_headers,
            json={"name": "Blog Writer", "description": "Writes blog posts"},
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name"] == "Blog Writer"
        assert data["description"] == "Writes blog posts"

    async def test_duplicate_name_conflict(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Two agents with the same name conflict."""
        await _create_agent(client, superuser_headers)

        response = await client.post(
            "/agents/", headers=superuser_headers, json={"name": "Blog Writer"}
        )

        assert response.status_code == 409

    async def test_requires_auth(self, client: AsyncClient):
        """Creating an agent without auth is rejected."""
        response = await client.post("/agents/", json={"name": "Blog Writer"})
        assert response.status_code == 401

    async def test_regular_user_forbidden(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """A regular user cannot create an agent."""
        response = await client.post(
            "/agents/", headers=auth_headers, json={"name": "Blog Writer"}
        )
        assert response.status_code == 403


class TestListAndGetAgents:
    """Tests for GET /agents/ and /{id}."""

    async def test_lists_agents_as_regular_user(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        auth_headers: dict[str, str],
    ):
        """Any authenticated user can list agents."""
        await _create_agent(client, superuser_headers)

        response = await client.get("/agents/", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_filters_by_project_type(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """Filtering by project_type_id returns only linked agents."""
        agent_id = await _create_agent(client, superuser_headers)
        await client.post(
            "/agent-project-types/",
            headers=superuser_headers,
            json={"agent_id": agent_id, "project_type_id": str(project_type.id)},
        )

        response = await client.get(
            f"/agents/?project_type_id={project_type.id}", headers=superuser_headers
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == agent_id

    async def test_filter_excludes_unlinked_agents(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """An agent not linked to the project type is not returned by the filter."""
        await _create_agent(client, superuser_headers)

        response = await client.get(
            f"/agents/?project_type_id={project_type.id}", headers=superuser_headers
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_get_agent(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """An agent is readable by id (superuser)."""
        agent_id = await _create_agent(client, superuser_headers)

        response = await client.get(f"/agents/{agent_id}", headers=superuser_headers)

        assert response.status_code == 200
        assert response.json()["id"] == agent_id

    async def test_get_unknown_not_found(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Reading a non-existent agent returns 404."""
        response = await client.get(
            f"/agents/{uuid.uuid4()}", headers=superuser_headers
        )
        assert response.status_code == 404


class TestUpdateAgent:
    """Tests for PATCH /agents/{id}."""

    async def test_updates_agent(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A superuser renames an agent."""
        agent_id = await _create_agent(client, superuser_headers)

        response = await client.patch(
            f"/agents/{agent_id}",
            headers=superuser_headers,
            json={"name": "Catalogue Organiser"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Catalogue Organiser"


class TestDeleteAgent:
    """Tests for DELETE /agents/{id}."""

    async def test_deletes_agent(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """A superuser deletes an agent and it is then gone."""
        agent_id = await _create_agent(client, superuser_headers)

        response = await client.delete(f"/agents/{agent_id}", headers=superuser_headers)

        assert response.status_code == 204

        follow_up = await client.get(f"/agents/{agent_id}", headers=superuser_headers)
        assert follow_up.status_code == 404
