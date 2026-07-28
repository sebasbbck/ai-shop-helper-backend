"""Integration tests for the /orgs router."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _roles(seeded_roles: object) -> None:
    """Ensure base roles exist for every org test (org creation needs Owner)."""


class TestCreateOrg:
    """Tests for POST /orgs/."""

    async def test_creates_org_with_owner_and_free_credits(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Creating an org returns it and grants the free-tier purchased credits."""
        response = await client.post(
            "/orgs/", headers=auth_headers, json={"name": "Acme"}
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name"] == "Acme"
        assert data["purchased_credits"] > 0

    async def test_requires_auth(self, client: AsyncClient):
        """Creating an org without auth is rejected."""
        response = await client.post("/orgs/", json={"name": "Acme"})
        assert response.status_code == 401

    async def test_rejects_blank_name(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """A blank org name fails validation."""
        response = await client.post("/orgs/", headers=auth_headers, json={"name": ""})
        assert response.status_code == 422


class TestListOrgs:
    """Tests for GET /orgs/."""

    async def test_lists_only_member_orgs(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """The list returns orgs the caller belongs to, with nested projects."""
        await client.post("/orgs/", headers=auth_headers, json={"name": "Mine"})

        response = await client.get("/orgs/", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Mine"
        assert body["items"][0]["projects"] == []


class TestGetOrg:
    """Tests for GET /orgs/{org_id}."""

    async def test_get_own_org(self, client: AsyncClient, auth_headers: dict[str, str]):
        """A member can read their org by id."""
        created = await client.post(
            "/orgs/", headers=auth_headers, json={"name": "Readable"}
        )
        org_id = created.json()["id"]

        response = await client.get(f"/orgs/{org_id}", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["id"] == org_id

    async def test_non_member_forbidden(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        superuser_headers: dict[str, str],
    ):
        """A non-member cannot read someone else's org."""
        created = await client.post(
            "/orgs/", headers=auth_headers, json={"name": "Private"}
        )
        org_id = created.json()["id"]

        response = await client.get(f"/orgs/{org_id}", headers=superuser_headers)

        assert response.status_code == 403


class TestUpdateOrg:
    """Tests for PATCH /orgs/{org_id}."""

    async def test_owner_renames_org(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """The owner can rename their org."""
        created = await client.post(
            "/orgs/", headers=auth_headers, json={"name": "Old"}
        )
        org_id = created.json()["id"]

        response = await client.patch(
            f"/orgs/{org_id}", headers=auth_headers, json={"name": "New"}
        )

        assert response.status_code == 200
        assert response.json()["name"] == "New"


class TestDeleteOrg:
    """Tests for DELETE /orgs/{org_id}."""

    async def test_delete_missing_org(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Deleting a non-existent org is rejected before any delete happens."""
        response = await client.delete(f"/orgs/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code in (403, 404)
