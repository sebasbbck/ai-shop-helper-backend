"""Integration tests for the /connections/prestashop router — paste-a-key connect + status."""

import base64
import uuid
from collections.abc import Callable, Coroutine

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.connections.prestashop import PrestashopProvider
from ai_shop_helper_backend.models.connections import ConnectionType
from ai_shop_helper_backend.models.org_users import OrgUser
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.models.project_types import ProjectType
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.services import connections as conn_service


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


async def _login_headers(client: AsyncClient, owner: User) -> dict[str, str]:
    login = await client.post(
        "/auth/login",
        data={"username": owner.email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


class TestConnectPrestashop:
    async def test_connect_stores_connection_and_returns_status(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="ps-owner@example.com")
        project = await _make_project(session, owner)
        headers = await _login_headers(client, owner)

        response = await client.post(
            f"/connections/prestashop/{project.id}",
            headers=headers,
            json={"shop_url": "https://shop.test/", "ws_key": "WSKEY123"},
        )

        assert response.status_code == 200, response.text
        assert response.json() == {"connected": True, "shop_url": "https://shop.test"}

    async def test_connect_persists_prestashop_auth_shape(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="ps-auth@example.com")
        project = await _make_project(session, owner)
        headers = await _login_headers(client, owner)

        await client.post(
            f"/connections/prestashop/{project.id}",
            headers=headers,
            json={"shop_url": "https://shop.test", "ws_key": "WSKEY123"},
        )

        connection = await conn_service.get_connection_by_project_and_type(
            session, project.id, ConnectionType.prestashop
        )
        assert connection is not None
        provider = PrestashopProvider()
        credentials = await provider.get_credentials(session, connection)
        injected = provider.to_injected_inputs(credentials)
        assert injected["url"] == "https://shop.test/api"
        assert base64.b64decode(injected["auth_token"]).decode() == "WSKEY123:"

    async def test_requires_project_membership(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ) -> None:
        owner = await create_user(email="ps-other@example.com")
        project = await _make_project(session, owner)

        response = await client.post(
            f"/connections/prestashop/{project.id}",
            headers=auth_headers,
            json={"shop_url": "https://shop.test", "ws_key": "k"},
        )

        assert response.status_code == 403


class TestPrestashopStatus:
    async def test_not_connected_by_default(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="ps-status@example.com")
        project = await _make_project(session, owner)
        headers = await _login_headers(client, owner)

        response = await client.get(
            f"/connections/prestashop/{project.id}", headers=headers
        )

        assert response.status_code == 200
        assert response.json()["connected"] is False

    async def test_status_after_connect_hides_key(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="ps-hide@example.com")
        project = await _make_project(session, owner)
        headers = await _login_headers(client, owner)

        await client.post(
            f"/connections/prestashop/{project.id}",
            headers=headers,
            json={"shop_url": "https://shop.test", "ws_key": "SECRETKEY"},
        )

        response = await client.get(
            f"/connections/prestashop/{project.id}", headers=headers
        )

        assert response.json() == {"connected": True, "shop_url": "https://shop.test"}
        assert "SECRETKEY" not in response.text
