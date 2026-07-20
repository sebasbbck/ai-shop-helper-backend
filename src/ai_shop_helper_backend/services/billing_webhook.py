import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import stripe
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from stripe._stripe_object import UntypedStripeObject

from ai_shop_helper_backend.core.constants import SUB_BY_KEY, credits_for_topup
from ai_shop_helper_backend.models.billing import StripeSubscription
from ai_shop_helper_backend.services.billing_fulfillment import fulfill
from ai_shop_helper_backend.services.orgs import get_org_by_id

logger = logging.getLogger(__name__)


async def handle_event(session: AsyncSession, event: stripe.Event) -> None:
    """Dispatch a verified Stripe webhook event to the appropriate handler."""
    event_type: str = event.type
    logger.debug("stripe webhook received: %s", event_type)

    if event_type in (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    ):
        await _handle_checkout_session(session, event.data.object)
    elif event_type == "invoice.paid":
        await _handle_invoice_paid(session, event.data.object)
    elif event_type == "invoice.payment_failed":
        await _handle_invoice_payment_failed(session, event.data.object)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(session, event.data.object)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(session, event.data.object)
    else:
        logger.debug("stripe webhook ignored: %s", event_type)


async def _handle_checkout_session(
    session: AsyncSession, cs: UntypedStripeObject[Any]
) -> None:
    if cs.payment_status != "paid":
        return

    metadata = cs.metadata.to_dict() if cs.metadata else {}
    org_id_raw = metadata.get("org_id")
    if not org_id_raw:
        return

    org = await get_org_by_id(session, UUID(org_id_raw))
    if not org:
        return

    kind = metadata.get("kind")
    cs_id: str = cs.id

    if kind == "topup":
        credits = credits_for_topup(cs.amount_total or 0)
        await fulfill(
            session, org, kind="topup", credits=credits, dedupe_key=f"cs_{cs_id}"
        )
        logger.info(
            "stripe topup fulfilled: cs_%s org=%s credits=%d",
            cs_id,
            org_id_raw,
            credits,
        )

    elif kind == "subscription":
        plan_key = metadata.get("plan_key")
        if plan_key not in SUB_BY_KEY:
            return
        credits = SUB_BY_KEY[plan_key].credits
        sub_id = getattr(cs, "subscription", None)
        await fulfill(
            session,
            org,
            kind="subscription",
            credits=credits,
            plan_key=plan_key,
            stripe_subscription_id=sub_id,
            dedupe_key=f"cs_{cs_id}",
        )
        logger.info(
            "stripe subscription checkout fulfilled: cs_%s org=%s plan=%s credits=%d",
            cs_id,
            org_id_raw,
            plan_key,
            credits,
        )


async def _handle_invoice_paid(
    session: AsyncSession, inv: UntypedStripeObject[Any]
) -> None:
    if getattr(inv, "billing_reason", None) != "subscription_cycle":
        return

    sub_id = getattr(inv, "subscription", None)
    if not sub_id:
        return

    result = await session.exec(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == sub_id
        )
    )
    sub_row = result.first()
    if not sub_row:
        return

    org = await get_org_by_id(session, sub_row.org_id)
    if not org:
        return

    period_end_ts = getattr(inv, "period_end", None)
    if period_end_ts is not None:
        sub_row.current_period_end = datetime.fromtimestamp(period_end_ts)
        session.add(sub_row)

    credits = sub_row.credits_per_cycle
    inv_id: str = inv.id
    await fulfill(
        session,
        org,
        kind="subscription",
        credits=credits,
        plan_key=sub_row.plan,
        stripe_subscription_id=sub_id,
        dedupe_key=f"inv_{inv_id}",
    )
    logger.info(
        "stripe subscription renewal fulfilled: inv_%s org=%s credits=%d",
        inv_id,
        str(sub_row.org_id),
        credits,
    )


async def _handle_invoice_payment_failed(
    session: AsyncSession, inv: UntypedStripeObject[Any]
) -> None:
    sub_id = getattr(inv, "subscription", None)
    if not sub_id:
        return

    result = await session.exec(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == sub_id
        )
    )
    sub_row = result.first()
    if sub_row:
        sub_row.status = "past_due"
        session.add(sub_row)
        logger.info("stripe subscription past_due: sub=%s", sub_id)


async def _handle_subscription_updated(
    session: AsyncSession, sub: UntypedStripeObject[Any]
) -> None:
    result = await session.exec(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == sub.id
        )
    )
    sub_row = result.first()
    if not sub_row:
        return

    sub_row.status = sub.status
    period_end_ts = getattr(sub, "current_period_end", None)
    if period_end_ts is not None:
        sub_row.current_period_end = datetime.fromtimestamp(period_end_ts)
    session.add(sub_row)
    logger.info("stripe subscription updated: sub=%s status=%s", sub.id, sub.status)


async def _handle_subscription_deleted(
    session: AsyncSession, sub: UntypedStripeObject[Any]
) -> None:
    result = await session.exec(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == sub.id
        )
    )
    sub_row = result.first()
    if sub_row:
        sub_row.status = "canceled"
        session.add(sub_row)
        logger.info("stripe subscription canceled: sub=%s", sub.id)
