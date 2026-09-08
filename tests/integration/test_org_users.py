"""Integration tests for the /orgs members router."""

import uuid
from collections.abc import Callable, Coroutine

import pytest
from httpx import AsyncClient

from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.models.users import User


@pytest.fixture(autouse=True)
def _roles(seeded_roles: object) -> None:
    """Ensure base roles exist for every member test (org creation needs Owner)."""


async def _create_org(client: AsyncClient, headers: dict[str, str]) -> str:
    """Create an org as the caller and return its id."""
    response = await client.post("/orgs/", headers=headers, json={"name": "Acme"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestAddOrgMember:
    """Tests for POST /orgs/{org_id}/members."""

    async def test_adds_member(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_roles: dict[str, Role],
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """An admin adds a second user as a Member."""
        org_id = await _create_org(client, auth_headers)
        member = await create_user(email="member@example.com")

        response = await client.post(
            f"/orgs/{org_id}/members",
            headers=auth_headers,
            json={
                "user_id": str(member.id),
                "org_id": org_id,
                "role_id": str(seeded_roles["Member"].id),
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["user_id"] == str(member.id)
        assert data["role_id"] == str(seeded_roles["Member"].id)

    async def test_rejects_org_id_mismatch(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_roles: dict[str, Role],
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """A body org_id that differs from the path is rejected."""
        org_id = await _create_org(client, auth_headers)
        member = await create_user(email="member@example.com")

        response = await client.post(
            f"/orgs/{org_id}/members",
            headers=auth_headers,
            json={
                "user_id": str(member.id),
                "org_id": str(uuid.uuid4()),
                "role_id": str(seeded_roles["Member"].id),
            },
        )

        assert response.status_code == 400

    async def test_unknown_user_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_roles: dict[str, Role],
    ):
        """Adding a non-existent user returns 404."""
        org_id = await _create_org(client, auth_headers)

        response = await client.post(
            f"/orgs/{org_id}/members",
            headers=auth_headers,
            json={
                "user_id": str(uuid.uuid4()),
                "org_id": org_id,
                "role_id": str(seeded_roles["Member"].id),
            },
        )

        assert response.status_code == 404

    async def test_duplicate_member_conflict(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_roles: dict[str, Role],
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """Adding the same user twice conflicts."""
        org_id = await _create_org(client, auth_headers)
        member = await create_user(email="member@example.com")
        body = {
            "user_id": str(member.id),
            "org_id": org_id,
            "role_id": str(seeded_roles["Member"].id),
        }
        await client.post(f"/orgs/{org_id}/members", headers=auth_headers, json=body)

        response = await client.post(
            f"/orgs/{org_id}/members", headers=auth_headers, json=body
        )

        assert response.status_code == 409

    async def test_requires_auth(
        self, client: AsyncClient, seeded_roles: dict[str, Role]
    ):
        """Adding a member without auth is rejected."""
        org_id = str(uuid.uuid4())
        response = await client.post(
            f"/orgs/{org_id}/members",
            json={
                "user_id": str(uuid.uuid4()),
                "org_id": org_id,
                "role_id": str(seeded_roles["Member"].id),
            },
        )
        assert response.status_code == 401

    async def test_non_member_forbidden(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        superuser_headers: dict[str, str],
        seeded_roles: dict[str, Role],
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """A non-member cannot add members to someone else's org."""
        org_id = await _create_org(client, auth_headers)
        target = await create_user(email="target@example.com")

        response = await client.post(
            f"/orgs/{org_id}/members",
            headers=superuser_headers,
            json={
                "user_id": str(target.id),
                "org_id": org_id,
                "role_id": str(seeded_roles["Member"].id),
            },
        )

        assert response.status_code == 403


class TestListAndGetMembers:
    """Tests for GET /orgs/{org_id}/members and /{user_id}."""

    async def test_lists_members(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_roles: dict[str, Role],
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """The list includes the owner and the added member."""
        org_id = await _create_org(client, auth_headers)
        member = await create_user(email="member@example.com")
        await client.post(
            f"/orgs/{org_id}/members",
            headers=auth_headers,
            json={
                "user_id": str(member.id),
                "org_id": org_id,
                "role_id": str(seeded_roles["Member"].id),
            },
        )

        response = await client.get(f"/orgs/{org_id}/members", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        added = next(
            row for row in data["items"] if row["user"]["id"] == str(member.id)
        )
        assert added["user"]["email"] == "member@example.com"
        assert added["role"]["name"] == "Member"
        assert added["role"]["access_level"] == seeded_roles["Member"].access_level

    async def test_get_member(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_roles: dict[str, Role],
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """A member is readable by user id."""
        org_id = await _create_org(client, auth_headers)
        member = await create_user(email="member@example.com")
        await client.post(
            f"/orgs/{org_id}/members",
            headers=auth_headers,
            json={
                "user_id": str(member.id),
                "org_id": org_id,
                "role_id": str(seeded_roles["Member"].id),
            },
        )

        response = await client.get(
            f"/orgs/{org_id}/members/{member.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["id"] == str(member.id)
        assert data["user"]["email"] == "member@example.com"
        assert data["role"]["name"] == "Member"

    async def test_get_unknown_member_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Reading a non-existent member returns 404."""
        org_id = await _create_org(client, auth_headers)

        response = await client.get(
            f"/orgs/{org_id}/members/{uuid.uuid4()}", headers=auth_headers
        )

        assert response.status_code == 404


class TestUpdateMemberRole:
    """Tests for PATCH /orgs/{org_id}/members/{user_id}."""

    async def test_updates_role(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_roles: dict[str, Role],
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """An admin promotes a Member to Admin."""
        org_id = await _create_org(client, auth_headers)
        member = await create_user(email="member@example.com")
        await client.post(
            f"/orgs/{org_id}/members",
            headers=auth_headers,
            json={
                "user_id": str(member.id),
                "org_id": org_id,
                "role_id": str(seeded_roles["Member"].id),
            },
        )

        response = await client.patch(
            f"/orgs/{org_id}/members/{member.id}",
            headers=auth_headers,
            json={"role_id": str(seeded_roles["Admin"].id)},
        )

        assert response.status_code == 200
        assert response.json()["role_id"] == str(seeded_roles["Admin"].id)


class TestRemoveMember:
    """Tests for DELETE /orgs/{org_id}/members/{user_id}."""

    async def test_removes_member(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seeded_roles: dict[str, Role],
        create_user: Callable[..., Coroutine[None, None, User]],
    ):
        """An admin removes a member and it is then gone."""
        org_id = await _create_org(client, auth_headers)
        member = await create_user(email="member@example.com")
        await client.post(
            f"/orgs/{org_id}/members",
            headers=auth_headers,
            json={
                "user_id": str(member.id),
                "org_id": org_id,
                "role_id": str(seeded_roles["Member"].id),
            },
        )

        response = await client.delete(
            f"/orgs/{org_id}/members/{member.id}", headers=auth_headers
        )

        assert response.status_code == 204

        follow_up = await client.get(
            f"/orgs/{org_id}/members/{member.id}", headers=auth_headers
        )
        assert follow_up.status_code == 404
