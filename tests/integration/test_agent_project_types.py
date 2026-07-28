"""Integration tests for the /agent-project-types router (superuser only)."""

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


class TestCreateAgentProjectType:
    """Tests for POST /agent-project-types/."""

    async def test_links_agent_to_project_type(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """A superuser links an agent to a project type."""
        agent_id = await _create_agent(client, superuser_headers)

        response = await client.post(
            "/agent-project-types/",
            headers=superuser_headers,
            json={"agent_id": agent_id, "project_type_id": str(project_type.id)},
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["agent_id"] == agent_id
        assert data["project_type_id"] == str(project_type.id)

    async def test_unknown_agent_not_found(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """Linking a non-existent agent returns 404."""
        response = await client.post(
            "/agent-project-types/",
            headers=superuser_headers,
            json={
                "agent_id": str(uuid.uuid4()),
                "project_type_id": str(project_type.id),
            },
        )

        assert response.status_code == 404

    async def test_unknown_project_type_not_found(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Linking to a non-existent project type returns 404."""
        agent_id = await _create_agent(client, superuser_headers)

        response = await client.post(
            "/agent-project-types/",
            headers=superuser_headers,
            json={"agent_id": agent_id, "project_type_id": str(uuid.uuid4())},
        )

        assert response.status_code == 404

    async def test_duplicate_link_conflict(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """Linking the same agent and project type twice conflicts."""
        agent_id = await _create_agent(client, superuser_headers)
        body = {"agent_id": agent_id, "project_type_id": str(project_type.id)}
        await client.post("/agent-project-types/", headers=superuser_headers, json=body)

        response = await client.post(
            "/agent-project-types/", headers=superuser_headers, json=body
        )

        assert response.status_code == 409

    async def test_requires_auth(self, client: AsyncClient, project_type: ProjectType):
        """Linking without auth is rejected."""
        response = await client.post(
            "/agent-project-types/",
            json={
                "agent_id": str(uuid.uuid4()),
                "project_type_id": str(project_type.id),
            },
        )
        assert response.status_code == 401

    async def test_regular_user_forbidden(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """A regular user cannot link agents to project types."""
        response = await client.post(
            "/agent-project-types/",
            headers=auth_headers,
            json={
                "agent_id": str(uuid.uuid4()),
                "project_type_id": str(project_type.id),
            },
        )
        assert response.status_code == 403


class TestListAndGetAgentProjectTypes:
    """Tests for GET /agent-project-types/ and /{id}."""

    async def test_lists_links(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """The list returns created links."""
        agent_id = await _create_agent(client, superuser_headers)
        await client.post(
            "/agent-project-types/",
            headers=superuser_headers,
            json={"agent_id": agent_id, "project_type_id": str(project_type.id)},
        )

        response = await client.get("/agent-project-types/", headers=superuser_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_get_link(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """A link is readable by id."""
        agent_id = await _create_agent(client, superuser_headers)
        created = await client.post(
            "/agent-project-types/",
            headers=superuser_headers,
            json={"agent_id": agent_id, "project_type_id": str(project_type.id)},
        )
        apt_id = created.json()["id"]

        response = await client.get(
            f"/agent-project-types/{apt_id}", headers=superuser_headers
        )

        assert response.status_code == 200
        assert response.json()["id"] == apt_id

    async def test_get_unknown_not_found(
        self, client: AsyncClient, superuser_headers: dict[str, str]
    ):
        """Reading a non-existent link returns 404."""
        response = await client.get(
            f"/agent-project-types/{uuid.uuid4()}", headers=superuser_headers
        )
        assert response.status_code == 404


class TestDeleteAgentProjectType:
    """Tests for DELETE /agent-project-types/{id}."""

    async def test_deletes_link(
        self,
        client: AsyncClient,
        superuser_headers: dict[str, str],
        project_type: ProjectType,
    ):
        """A superuser deletes a link and it is then gone."""
        agent_id = await _create_agent(client, superuser_headers)
        created = await client.post(
            "/agent-project-types/",
            headers=superuser_headers,
            json={"agent_id": agent_id, "project_type_id": str(project_type.id)},
        )
        apt_id = created.json()["id"]

        response = await client.delete(
            f"/agent-project-types/{apt_id}", headers=superuser_headers
        )

        assert response.status_code == 204

        follow_up = await client.get(
            f"/agent-project-types/{apt_id}", headers=superuser_headers
        )
        assert follow_up.status_code == 404
