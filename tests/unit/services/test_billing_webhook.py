"""Unit tests for services/billing_webhook.py — all DB, Stripe, and service calls mocked."""

from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.services import billing_webhook


def _make_event(event_type: str, obj) -> SimpleNamespace:
    return SimpleNamespace(type=event_type, data=SimpleNamespace(object=obj))


def _make_cs(
    *,
    payment_status: str = "paid",
    org_id: str = "11111111-1111-1111-1111-111111111111",
    kind: str = "topup",
    amount_total: int = 2500,
    cs_id: str = "cs_test_001",
    plan_key: str | None = None,
    subscription: str | None = None,
) -> SimpleNamespace:
    metadata = {"org_id": org_id, "kind": kind}
    if plan_key:
        metadata["plan_key"] = plan_key
    return SimpleNamespace(
        id=cs_id,
        payment_status=payment_status,
        metadata=SimpleNamespace(to_dict=lambda md=metadata: md),
        amount_total=amount_total,
        subscription=subscription,
    )


def _make_invoice(
    *,
    billing_reason: str = "subscription_cycle",
    subscription: str | None = "sub_001",
    inv_id: str = "inv_001",
    period_end: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=inv_id,
        billing_reason=billing_reason,
        subscription=subscription,
        period_end=period_end,
    )


def _make_subscription_obj(
    *,
    sub_id: str = "sub_001",
    sub_status: str = "active",
    current_period_end: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=sub_id, status=sub_status, current_period_end=current_period_end
    )


class TestCheckoutSessionCompletedTopup:
    """checkout.session.completed with kind=topup."""

    async def test_topup_paid_calls_fulfill(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Paid topup checkout calls fulfill with kind=topup and computed credits."""
        org = make_org()
        cs = _make_cs(kind="topup", amount_total=2500, cs_id="cs_topup_01")
        event = _make_event("checkout.session.completed", cs)

        with (
            patch(
                "ai_shop_helper_backend.services.billing_webhook.get_org_by_id",
                new_callable=AsyncMock,
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.billing_webhook.fulfill",
                new_callable=AsyncMock,
            ) as mock_fulfill,
        ):
            await billing_webhook.handle_event(mock_session, event)

        mock_fulfill.assert_awaited_once()
        call_kwargs = mock_fulfill.call_args.kwargs
        assert call_kwargs["kind"] == "topup"
        assert call_kwargs["credits"] == 2500
        assert call_kwargs["dedupe_key"] == "cs_cs_topup_01"

    async def test_topup_async_payment_succeeded_also_handled(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """checkout.session.async_payment_succeeded is treated the same as completed."""
        org = make_org()
        cs = _make_cs(kind="topup", amount_total=1000, cs_id="cs_async_01")
        event = _make_event("checkout.session.async_payment_succeeded", cs)

        with (
            patch(
                "ai_shop_helper_backend.services.billing_webhook.get_org_by_id",
                new_callable=AsyncMock,
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.billing_webhook.fulfill",
                new_callable=AsyncMock,
            ) as mock_fulfill,
        ):
            await billing_webhook.handle_event(mock_session, event)

        mock_fulfill.assert_awaited_once()
        assert mock_fulfill.call_args.kwargs["credits"] == 1000


class TestCheckoutSessionCompletedNotPaid:
    """checkout.session.completed when payment_status != 'paid'."""

    async def test_not_paid_does_not_call_fulfill(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Unpaid checkout session must not trigger fulfill."""
        cs = _make_cs(payment_status="unpaid", kind="topup", amount_total=500)
        event = _make_event("checkout.session.completed", cs)

        with patch(
            "ai_shop_helper_backend.services.billing_webhook.fulfill",
            new_callable=AsyncMock,
        ) as mock_fulfill:
            await billing_webhook.handle_event(mock_session, event)

        mock_fulfill.assert_not_awaited()


class TestCheckoutSessionCompletedSubscription:
    """checkout.session.completed with kind=subscription."""

    async def test_subscription_paid_calls_fulfill_with_plan_credits(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Paid subscription checkout calls fulfill with kind=subscription and plan credits."""
        org = make_org()
        cs = _make_cs(
            kind="subscription",
            plan_key="pro",
            cs_id="cs_sub_01",
            subscription="sub_stripe_01",
        )
        event = _make_event("checkout.session.completed", cs)

        with (
            patch(
                "ai_shop_helper_backend.services.billing_webhook.get_org_by_id",
                new_callable=AsyncMock,
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.billing_webhook.fulfill",
                new_callable=AsyncMock,
            ) as mock_fulfill,
        ):
            await billing_webhook.handle_event(mock_session, event)

        mock_fulfill.assert_awaited_once()
        call_kwargs = mock_fulfill.call_args.kwargs
        assert call_kwargs["kind"] == "subscription"
        assert call_kwargs["credits"] == 2500
        assert call_kwargs["plan_key"] == "pro"
        assert call_kwargs["stripe_subscription_id"] == "sub_stripe_01"
        assert call_kwargs["dedupe_key"] == "cs_cs_sub_01"

    async def test_subscription_unknown_plan_key_skips_fulfill(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Subscription checkout with an unrecognised plan_key must not call fulfill."""
        org = make_org()
        cs = _make_cs(kind="subscription", plan_key="unknown_tier", cs_id="cs_sub_bad")
        event = _make_event("checkout.session.completed", cs)

        with (
            patch(
                "ai_shop_helper_backend.services.billing_webhook.get_org_by_id",
                new_callable=AsyncMock,
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.billing_webhook.fulfill",
                new_callable=AsyncMock,
            ) as mock_fulfill,
        ):
            await billing_webhook.handle_event(mock_session, event)

        mock_fulfill.assert_not_awaited()


class TestInvoicePaid:
    """invoice.paid event handling."""

    async def test_subscription_cycle_calls_fulfill(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """invoice.paid with billing_reason=subscription_cycle grants renewal credits."""
        org = make_org()
        inv = _make_invoice(
            billing_reason="subscription_cycle",
            subscription="sub_001",
            inv_id="inv_123",
        )

        sub_row = MagicMock()
        sub_row.org_id = org.id
        sub_row.credits_per_cycle = 500
        sub_row.plan = "starter"

        exec_result = MagicMock()
        exec_result.first.return_value = sub_row
        mock_session.exec = AsyncMock(return_value=exec_result)

        event = _make_event("invoice.paid", inv)

        with (
            patch(
                "ai_shop_helper_backend.services.billing_webhook.get_org_by_id",
                new_callable=AsyncMock,
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.billing_webhook.fulfill",
                new_callable=AsyncMock,
            ) as mock_fulfill,
        ):
            await billing_webhook.handle_event(mock_session, event)

        mock_fulfill.assert_awaited_once()
        call_kwargs = mock_fulfill.call_args.kwargs
        assert call_kwargs["kind"] == "subscription"
        assert call_kwargs["credits"] == 500
        assert call_kwargs["dedupe_key"] == "inv_inv_123"

    async def test_subscription_create_reason_skips_fulfill(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """invoice.paid with billing_reason=subscription_create must not call fulfill."""
        inv = _make_invoice(billing_reason="subscription_create", inv_id="inv_first")
        event = _make_event("invoice.paid", inv)

        with patch(
            "ai_shop_helper_backend.services.billing_webhook.fulfill",
            new_callable=AsyncMock,
        ) as mock_fulfill:
            await billing_webhook.handle_event(mock_session, event)

        mock_fulfill.assert_not_awaited()

    async def test_manual_reason_skips_fulfill(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """invoice.paid with billing_reason=manual must not call fulfill."""
        inv = _make_invoice(billing_reason="manual", inv_id="inv_manual")
        event = _make_event("invoice.paid", inv)

        with patch(
            "ai_shop_helper_backend.services.billing_webhook.fulfill",
            new_callable=AsyncMock,
        ) as mock_fulfill:
            await billing_webhook.handle_event(mock_session, event)

        mock_fulfill.assert_not_awaited()


class TestUnknownEventType:
    """Unknown event types must be silently ignored."""

    async def test_unknown_event_does_not_call_fulfill(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Unrecognised event type returns without calling fulfill."""
        event = _make_event("payment_intent.created", SimpleNamespace(id="pi_001"))

        with patch(
            "ai_shop_helper_backend.services.billing_webhook.fulfill",
            new_callable=AsyncMock,
        ) as mock_fulfill:
            await billing_webhook.handle_event(mock_session, event)

        mock_fulfill.assert_not_awaited()
