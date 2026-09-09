"""Integration tests for GET /connections/{project_id}/available."""

import uuid
from collections.abc import Callable, Coroutine

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.models.agent_project_types import AgentProjectType
from ai_shop_helper_backend.models.agent_runs import AgentStep, RunnerType
from ai_shop_helper_backend.models.agents import Agent
from ai_shop_helper_backend.models.connections import ConnectionType
from ai_shop_helper_backend.models.org_users import OrgUser
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.models.project_types import ProjectType
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.services.connections import upsert_connection


async def _make_project(session: AsyncSession, owner: User) -> Project:
    role = Role(
        name=f"owner-{uuid.uuid4()}",
        access_level=0,
        created_by=owner.id,
        updated_by=owner.id,
    )
    session.add(role)
    await session.flush()

    org = Org(name=f"org-{uuid.uuid4()}", created_by=owner.id, updated_by=owner.id)
    session.add(org)
    await session.flush()

    session.add(
        OrgUser(
            user_id=owner.id,
            org_id=org.id,
            role_id=role.id,
            created_by=owner.id,
            updated_by=owner.id,
        )
    )

    project_type = ProjectType(
        name=f"type-{uuid.uuid4()}", created_by=owner.id, updated_by=owner.id
    )
    session.add(project_type)
    await session.flush()

    project = Project(
        org_id=org.id,
        name=f"project-{uuid.uuid4()}",
        project_type_id=project_type.id,
        created_by=owner.id,
        updated_by=owner.id,
    )
    session.add(project)
    await session.flush()
    await session.commit()
    await session.refresh(project)
    return project


async def _wire_agent_step(
    session: AsyncSession,
    owner: User,
    project: Project,
    connection_type: ConnectionType | None,
    slug: str = "generate",
) -> None:
    """Give the project's project type an agent with a step needing `connection_type`."""
    agent = Agent(
        name=f"agent-{uuid.uuid4()}", created_by=owner.id, updated_by=owner.id
    )
    session.add(agent)
    await session.flush()

    session.add(
        AgentProjectType(
            agent_id=agent.id,
            project_type_id=project.project_type_id,
            created_by=owner.id,
            updated_by=owner.id,
        )
    )

    session.add(
        AgentStep(
            agent_id=agent.id,
            order=1,
            slug=slug,
            runner_type=RunnerType.n8n,
            runner_ref=f"ref-{slug}",
            connection_type=connection_type,
        )
    )
    await session.commit()


async def _login(client: AsyncClient, owner: User) -> dict[str, str]:
    login = await client.post(
        "/auth/login",
        data={"username": owner.email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


class TestAvailableConnections:
    async def test_no_agents_wired_returns_empty_list(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="no-agents@example.com")
        project = await _make_project(session, owner)
        headers = await _login(client, owner)

        response = await client.get(
            f"/connections/{project.id}/available", headers=headers
        )

        assert response.status_code == 200
        assert response.json() == []

    async def test_relevant_type_not_connected(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="relevant-unconnected@example.com")
        project = await _make_project(session, owner)
        await _wire_agent_step(session, owner, project, ConnectionType.wordpress)
        headers = await _login(client, owner)

        response = await client.get(
            f"/connections/{project.id}/available", headers=headers
        )

        assert response.status_code == 200
        assert response.json() == [{"connection_type": "wordpress", "connected": False}]

    async def test_relevant_type_already_connected(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="relevant-connected@example.com")
        project = await _make_project(session, owner)
        await _wire_agent_step(session, owner, project, ConnectionType.wordpress)
        await upsert_connection(
            session,
            project_id=project.id,
            connection_type=ConnectionType.wordpress,
            secrets={"site_url": "https://example.com"},
        )
        await session.commit()
        headers = await _login(client, owner)

        response = await client.get(
            f"/connections/{project.id}/available", headers=headers
        )

        assert response.status_code == 200
        assert response.json() == [{"connection_type": "wordpress", "connected": True}]

    async def test_irrelevant_type_is_not_listed_even_if_connected(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        """No agent of this project type uses Google — it must not show up,
        even though a (stale) Google connection exists for the project."""
        owner = await create_user(email="irrelevant-type@example.com")
        project = await _make_project(session, owner)
        await _wire_agent_step(session, owner, project, ConnectionType.wordpress)
        await upsert_connection(
            session,
            project_id=project.id,
            connection_type=ConnectionType.google,
            secrets={"google_email": "someone@example.com"},
        )
        await session.commit()
        headers = await _login(client, owner)

        response = await client.get(
            f"/connections/{project.id}/available", headers=headers
        )

        assert response.status_code == 200
        assert response.json() == [{"connection_type": "wordpress", "connected": False}]

    async def test_multiple_relevant_types_can_coexist(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="multi-type@example.com")
        project = await _make_project(session, owner)
        await _wire_agent_step(
            session, owner, project, ConnectionType.wordpress, slug="cms-step"
        )
        await _wire_agent_step(
            session, owner, project, ConnectionType.google, slug="analytics-step"
        )
        headers = await _login(client, owner)

        response = await client.get(
            f"/connections/{project.id}/available", headers=headers
        )

        assert response.status_code == 200
        assert {c["connection_type"] for c in response.json()} == {
            "wordpress",
            "google",
        }

    async def test_requires_project_membership(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ) -> None:
        owner = await create_user(email="available-other-owner@example.com")
        project = await _make_project(session, owner)

        response = await client.get(
            f"/connections/{project.id}/available", headers=auth_headers
        )

        assert response.status_code == 403
