"""Integration tests for the referral routers."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _roles(seeded_roles: object) -> None:
    """Ensure base roles exist (org creation needs the Owner role)."""


async def _create_org(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    """Create an org and return its id."""
    response = await client.post("/orgs/", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestReferralOverview:
    """Tests for GET /orgs/{org_id}/referral."""

    async def test_returns_code_reward_and_empty_referrals(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """A member sees a generated code, share link, reward config and no referrals yet."""
        org_id = await _create_org(client, auth_headers, "Acme")

        response = await client.get(f"/orgs/{org_id}/referral", headers=auth_headers)

        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["code"]) == 8
        assert body["share_url"].endswith(f"/register?ref={body['code']}")
        assert body["reward"]["referrer_credits"] > 0
        assert body["reward"]["monthly_cap"] > 0
        assert body["rewarded_this_month"] == 0
        assert body["referrals"] == []

    async def test_code_is_stable_across_calls(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """Repeated views return the same code rather than regenerating it."""
        org_id = await _create_org(client, auth_headers, "Acme")

        first = await client.get(f"/orgs/{org_id}/referral", headers=auth_headers)
        second = await client.get(f"/orgs/{org_id}/referral", headers=auth_headers)

        assert first.json()["code"] == second.json()["code"]

    async def test_non_member_forbidden(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        superuser_headers: dict[str, str],
    ) -> None:
        """A non-member cannot read another org's referral dashboard."""
        org_id = await _create_org(client, superuser_headers, "Other")

        response = await client.get(f"/orgs/{org_id}/referral", headers=auth_headers)

        assert response.status_code == 403

    async def test_requires_auth(self, client: AsyncClient) -> None:
        """The dashboard requires authentication."""
        response = await client.get(f"/orgs/{uuid.uuid4()}/referral")
        assert response.status_code == 401


class TestReferrerInfo:
    """Tests for the public GET /referral/{code}."""

    async def test_returns_org_name_without_auth(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """An unauthenticated referee can resolve a code to the referrer org name."""
        org_id = await _create_org(client, auth_headers, "Referrer Inc")
        overview = await client.get(f"/orgs/{org_id}/referral", headers=auth_headers)
        code = overview.json()["code"]

        response = await client.get(f"/referral/{code}")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["org_name"] == "Referrer Inc"
        assert body["referee_credits"] >= 0

    async def test_unknown_code_is_404(self, client: AsyncClient) -> None:
        """An unknown code returns 404."""
        response = await client.get("/referral/NOSUCHCODE")
        assert response.status_code == 404
