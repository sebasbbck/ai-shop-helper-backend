"""Integration tests for the /connections/google router — project-scoped GA4/GSC access."""

import uuid
from collections.abc import Callable, Coroutine
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.models.org_users import OrgUser
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.models.project_types import ProjectType
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.models.users import User

_GOOGLE_TOKEN_RESPONSE = {
    "access_token": "google-access-token",
    "refresh_token": "google-refresh-token",
    "expires_in": 3600,
    "scope": "openid email profile",
}


async def _make_project(session: AsyncSession, owner: User) -> Project:
    role = Role(name=f"owner-{uuid.uuid4()}", access_level=0)
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


class TestStartGoogleConnection:
    async def test_returns_auth_url_and_sets_state_cookie(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="conn-owner@example.com")
        project = await _make_project(session, owner)
        login = await client.post(
            "/auth/login",
            data={"username": owner.email, "password": "password123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = await client.get(
            f"/connections/google/{project.id}/start", headers=headers
        )

        assert response.status_code == 200
        assert "accounts.google.com" in response.json()["auth_url"]
        assert "oauth_connection_state" in response.cookies

    async def test_requires_project_membership(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ) -> None:
        owner = await create_user(email="other-owner@example.com")
        project = await _make_project(session, owner)

        response = await client.get(
            f"/connections/google/{project.id}/start", headers=auth_headers
        )

        assert response.status_code == 403


class TestGoogleConnectionStatus:
    async def test_not_connected_by_default(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="status-owner@example.com")
        project = await _make_project(session, owner)
        login = await client.post(
            "/auth/login",
            data={"username": owner.email, "password": "password123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = await client.get(
            f"/connections/google/{project.id}", headers=headers
        )

        assert response.status_code == 200
        assert response.json()["connected"] is False


class TestGoogleConnectionCallback:
    async def test_establishes_connection_and_redirects(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="callback-owner@example.com")
        project = await _make_project(session, owner)
        login = await client.post(
            "/auth/login",
            data={"username": owner.email, "password": "password123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        start = await client.get(
            f"/connections/google/{project.id}/start", headers=headers
        )
        state = start.cookies["oauth_connection_state"]
        client.cookies.set("oauth_connection_state", state)

        with (
            patch(
                "ai_shop_helper_backend.routers.connections.google_conn.exchange_code",
                new_callable=AsyncMock,
                return_value=_GOOGLE_TOKEN_RESPONSE,
            ),
            patch(
                "ai_shop_helper_backend.routers.connections.google_conn.get_userinfo",
                new_callable=AsyncMock,
                return_value={"email": "data@example.com"},
            ),
        ):
            response = await client.get(
                "/connections/google/callback", params={"code": "abc", "state": state}
            )

        assert response.status_code in (302, 307)
        assert response.headers["location"] == settings.WP_SUCCESS_FRONTEND_URL

        status_resp = await client.get(
            f"/connections/google/{project.id}", headers=headers
        )
        assert status_resp.json() == {
            "connected": True,
            "google_email": "data@example.com",
        }


class TestGoogleGA4Endpoints:
    async def test_returns_403_when_not_connected(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        owner = await create_user(email="ga4-owner@example.com")
        project = await _make_project(session, owner)
        login = await client.post(
            "/auth/login",
            data={"username": owner.email, "password": "password123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = await client.get(
            f"/connections/google/{project.id}/ga4/accounts", headers=headers
        )

        assert response.status_code == 403
