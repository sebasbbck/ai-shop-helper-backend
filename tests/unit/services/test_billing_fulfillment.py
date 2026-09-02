"""Unit tests for services/billing_fulfillment.py — all DB and service calls mocked."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy.exc

from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.services.billing_fulfillment import fulfill


@pytest.fixture(autouse=True)
def _stub_referral_hook() -> Generator[AsyncMock, None, None]:
    """Isolate fulfill from the referral reward hook it calls on success."""
    with patch(
        "ai_shop_helper_backend.services.billing_fulfillment.referrals.on_org_paid",
        new_callable=AsyncMock,
    ) as hook:
        yield hook


@pytest.fixture(autouse=True)
def _stub_notify_hook() -> Generator[AsyncMock, None, None]:
    """Isolate fulfill from the billing notification it dispatches on success."""
    with patch(
        "ai_shop_helper_backend.services.billing_fulfillment.notifications.notify_org_members_by_role",
        new_callable=AsyncMock,
    ) as hook:
        yield hook


class TestFulfillTopupPath:
    """Tests for the top-up (one-time purchase) fulfillment path."""

    async def test_topup_calls_grant_purchased(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """fulfill with kind='topup' calls billing.grant_purchased with the given credits."""
        org = make_org()
        mock_session.flush = AsyncMock()

        with (
            patch(
                "ai_shop_helper_backend.services.billing_fulfillment.billing.grant_purchased",
                new_callable=AsyncMock,
            ) as mock_grant,
            patch(
                "ai_shop_helper_backend.services.billing_fulfillment.billing.set_subscription_credits",
                new_callable=AsyncMock,
            ) as mock_sub,
        ):
            result = await fulfill(
                mock_session,
                org,
                kind="topup",
                credits=250,
                dedupe_key="cs_test_001",
            )

        assert result is True
        mock_grant.assert_called_once()
        assert mock_grant.call_args.args[2] == 250
        mock_sub.assert_not_called()

    async def test_topup_passes_correct_stripe_event_id(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """fulfill with kind='topup' passes dedupe_key as stripe_event_id to grant_purchased."""
        org = make_org()
        mock_session.flush = AsyncMock()
        dedupe = "cs_abc_xyz"

        with patch(
            "ai_shop_helper_backend.services.billing_fulfillment.billing.grant_purchased",
            new_callable=AsyncMock,
        ) as mock_grant:
            await fulfill(
                mock_session, org, kind="topup", credits=100, dedupe_key=dedupe
            )

        _, kwargs = mock_grant.call_args
        assert kwargs.get("stripe_event_id") == dedupe

    async def test_topup_credits_amount_passed_through(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """fulfill with kind='topup' grants exactly the credits passed in."""
        org = make_org()
        mock_session.flush = AsyncMock()

        with patch(
            "ai_shop_helper_backend.services.billing_fulfillment.billing.grant_purchased",
            new_callable=AsyncMock,
        ) as mock_grant:
            await fulfill(
                mock_session, org, kind="topup", credits=500, dedupe_key="cs_topup_1"
            )

        assert mock_grant.call_args.args[2] == 500

    async def test_topup_notifies_org_owners(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
        _stub_notify_hook: AsyncMock,
    ) -> None:
        """fulfill notifies org owners about the credits granted."""
        org = make_org()
        mock_session.flush = AsyncMock()

        with patch(
            "ai_shop_helper_backend.services.billing_fulfillment.billing.grant_purchased",
            new_callable=AsyncMock,
        ):
            await fulfill(
                mock_session, org, kind="topup", credits=250, dedupe_key="cs_notify_1"
            )

        _stub_notify_hook.assert_awaited_once()
        assert _stub_notify_hook.call_args.args[1] == org.id
        assert _stub_notify_hook.call_args.kwargs["payload"]["credits"] == 250


class TestFulfillSubscriptionPath:
    """Tests for the subscription renewal fulfillment path."""

    async def test_subscription_calls_set_subscription_credits(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """fulfill with kind='subscription' calls billing.set_subscription_credits."""
        org = make_org()
        mock_session.flush = AsyncMock()

        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=exec_result)

        with (
            patch(
                "ai_shop_helper_backend.services.billing_fulfillment.billing.set_subscription_credits",
                new_callable=AsyncMock,
            ) as mock_set,
            patch(
                "ai_shop_helper_backend.services.billing_fulfillment.billing.grant_purchased",
                new_callable=AsyncMock,
            ) as mock_grant,
        ):
            result = await fulfill(
                mock_session,
                org,
                kind="subscription",
                credits=500,
                dedupe_key="cs_sub_1",
                plan_key="starter",
                stripe_subscription_id="sub_test",
            )

        assert result is True
        mock_set.assert_called_once()
        mock_grant.assert_not_called()

    async def test_subscription_passes_credits_to_set_subscription_credits(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """fulfill with kind='subscription' passes the given credits to set_subscription_credits."""
        org = make_org()
        mock_session.flush = AsyncMock()

        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=exec_result)

        with patch(
            "ai_shop_helper_backend.services.billing_fulfillment.billing.set_subscription_credits",
            new_callable=AsyncMock,
        ) as mock_set:
            await fulfill(
                mock_session,
                org,
                kind="subscription",
                credits=2000,
                dedupe_key="cs_sub_2",
                plan_key="pro",
            )

        assert mock_set.call_args.args[2] == 2000


class TestFulfillIdempotency:
    """Tests for the deduplification guard in fulfill."""

    async def test_returns_false_on_duplicate_key(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """fulfill returns False without granting when the dedupe_key is already recorded."""
        org = make_org()
        mock_session.flush = AsyncMock(
            side_effect=sqlalchemy.exc.IntegrityError(None, None, Exception("unique"))
        )
        mock_session.rollback = AsyncMock()

        with (
            patch(
                "ai_shop_helper_backend.services.billing_fulfillment.billing.grant_purchased",
                new_callable=AsyncMock,
            ) as mock_grant,
            patch(
                "ai_shop_helper_backend.services.billing_fulfillment.billing.set_subscription_credits",
                new_callable=AsyncMock,
            ) as mock_set,
        ):
            result = await fulfill(
                mock_session,
                org,
                kind="topup",
                credits=100,
                dedupe_key="cs_already_done",
            )

        assert result is False
        mock_grant.assert_not_called()
        mock_set.assert_not_called()

    async def test_rolls_back_session_on_duplicate(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """fulfill calls session.rollback when IntegrityError is caught on flush."""
        org = make_org()
        mock_session.flush = AsyncMock(
            side_effect=sqlalchemy.exc.IntegrityError(None, None, Exception("unique"))
        )
        mock_session.rollback = AsyncMock()

        await fulfill(mock_session, org, kind="topup", credits=50, dedupe_key="cs_dup")

        mock_session.rollback.assert_called_once()


class TestConstantsHelpers:
    """Tests for constants helpers used by fulfillment and gateway."""

    def test_credits_for_topup_standard_amounts(self) -> None:
        """credits_for_topup returns floor-divided credits at 1 cent each."""
        from ai_shop_helper_backend.core.constants import credits_for_topup

        assert credits_for_topup(2500) == 2500
        assert credits_for_topup(500) == 500

    def test_credits_for_topup_one_credit_per_cent(self) -> None:
        """credits_for_topup grants one credit per cent."""
        from ai_shop_helper_backend.core.constants import credits_for_topup

        assert credits_for_topup(1999) == 1999

    def test_sub_by_key_contains_tiers(self) -> None:
        """SUB_BY_KEY holds pro/business/enterprise and no paid starter."""
        from ai_shop_helper_backend.core.constants import SUB_BY_KEY

        assert "starter" not in SUB_BY_KEY
        assert {"pro", "business", "enterprise"} <= set(SUB_BY_KEY)

    def test_business_tier_credits(self) -> None:
        """Business tier has 8000 credits at 5000 cents."""
        from ai_shop_helper_backend.core.constants import SUB_BY_KEY

        assert SUB_BY_KEY["business"].credits == 8000
        assert SUB_BY_KEY["business"].unit_amount == 5000

    def test_enterprise_tier_credits(self) -> None:
        """Enterprise tier has 20000 credits at 12000 cents."""
        from ai_shop_helper_backend.core.constants import SUB_BY_KEY

        assert SUB_BY_KEY["enterprise"].credits == 20000
        assert SUB_BY_KEY["enterprise"].unit_amount == 12000

    def test_pro_tier_credits(self) -> None:
        """Pro tier has 2500 credits at 2000 cents."""
        from ai_shop_helper_backend.core.constants import SUB_BY_KEY

        assert SUB_BY_KEY["pro"].credits == 2500
        assert SUB_BY_KEY["pro"].unit_amount == 2000

    def test_stripe_lookup_key_format(self) -> None:
        """stripe_lookup_key prefixes tier key with 'aish_'."""
        from ai_shop_helper_backend.core.constants import stripe_lookup_key

        assert stripe_lookup_key("starter") == "aish_starter"
        assert stripe_lookup_key("pro") == "aish_pro"

    def test_free_tier_credits(self) -> None:
        """FREE_TIER_CREDITS is 120."""
        from ai_shop_helper_backend.core.constants import FREE_TIER_CREDITS

        assert FREE_TIER_CREDITS == 120

    def test_topup_lookup_key(self) -> None:
        """TOPUP_LOOKUP_KEY is 'aish_topup'."""
        from ai_shop_helper_backend.core.constants import TOPUP_LOOKUP_KEY

        assert TOPUP_LOOKUP_KEY == "aish_topup"
