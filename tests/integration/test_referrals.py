"""Integration tests for the referral routers and end-to-end reward flow."""

import uuid
from collections.abc import Callable, Coroutine

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.constants import FREE_TIER_CREDITS, REFERRAL_REWARD
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.services import billing_fulfillment, users
from ai_shop_helper_backend.services.orgs import get_org_by_id


@pytest.fixture(autouse=True)
def _roles(seeded_roles: object) -> None:
    """Ensure base roles exist (org creation needs the Owner role)."""


async def _create_org(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    """Create an org and return its id."""
    response = await client.post("/orgs/", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
    """Log a user in and return Bearer auth headers."""
    response = await client.post(
        "/auth/login", data={"username": email, "password": "password123"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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


class TestReferralRewardFlow:
    """End-to-end tests exercising the three trigger hooks together."""

    async def test_full_reward_flow_across_all_hooks(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
        session: AsyncSession,
    ) -> None:
        """A referred org that pays real money rewards both referrer and referee."""
        await create_user(email="referrer@example.com")
        referrer_headers = await _login(client, "referrer@example.com")
        referrer_org_id = await _create_org(client, referrer_headers, "Referrer Inc")
        overview = await client.get(
            f"/orgs/{referrer_org_id}/referral", headers=referrer_headers
        )
        code = overview.json()["code"]

        register = await client.post(
            "/auth/register",
            json={
                "email": "referee@example.com",
                "name": "Referee",
                "password": "password123",
                "referral_code": code,
            },
        )
        assert register.status_code == 201, register.text

        referee = await users.get_user_by_email(session, "referee@example.com")
        assert referee is not None
        referee.email_verified = True
        session.add(referee)
        await session.commit()

        referee_headers = await _login(client, "referee@example.com")
        referee_org_id = await _create_org(client, referee_headers, "Referee LLC")

        referee_org = await get_org_by_id(session, uuid.UUID(referee_org_id))
        assert referee_org is not None
        await billing_fulfillment.fulfill(
            session, referee_org, kind="topup", credits=100, dedupe_key="cs_reftest"
        )
        await session.commit()

        referrer_balance = await client.get(
            f"/orgs/{referrer_org_id}/billing/balance", headers=referrer_headers
        )
        assert (
            referrer_balance.json()["purchased_credits"]
            == FREE_TIER_CREDITS + REFERRAL_REWARD.referrer_credits
        )

        referee_balance = await client.get(
            f"/orgs/{referee_org_id}/billing/balance", headers=referee_headers
        )
        assert (
            referee_balance.json()["purchased_credits"]
            == FREE_TIER_CREDITS + 100 + REFERRAL_REWARD.referee_credits
        )

        after = await client.get(
            f"/orgs/{referrer_org_id}/referral", headers=referrer_headers
        )
        body = after.json()
        assert body["rewarded_this_month"] == 1
        assert body["referrals"][0]["status"] == "rewarded"
        assert body["referrals"][0]["referee_org_id"] == referee_org_id

    async def test_register_with_unknown_code_still_succeeds(
        self, client: AsyncClient
    ) -> None:
        """An unknown referral code never blocks signup."""
        response = await client.post(
            "/auth/register",
            json={
                "email": "solo@example.com",
                "name": "Solo",
                "password": "password123",
                "referral_code": "NOSUCHCODE",
            },
        )
        assert response.status_code == 201

    async def test_payment_without_referral_is_harmless(
        self,
        client: AsyncClient,
        create_user: Callable[..., Coroutine[None, None, User]],
        session: AsyncSession,
    ) -> None:
        """Paying with no pending referral grants only the purchase, no phantom reward."""
        await create_user(email="plain@example.com")
        headers = await _login(client, "plain@example.com")
        org_id = await _create_org(client, headers, "Plain Co")

        org = await get_org_by_id(session, uuid.UUID(org_id))
        assert org is not None
        await billing_fulfillment.fulfill(
            session, org, kind="topup", credits=50, dedupe_key="cs_plain"
        )
        await session.commit()

        balance = await client.get(f"/orgs/{org_id}/billing/balance", headers=headers)
        assert balance.json()["purchased_credits"] == FREE_TIER_CREDITS + 50
