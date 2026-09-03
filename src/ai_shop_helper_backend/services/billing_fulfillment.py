from datetime import datetime

import sqlalchemy.exc
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.constants import AccessLevel, NotificationType
from ai_shop_helper_backend.models.billing import (
    StripeProcessedEvent,
    StripeSubscription,
)
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.services import billing, notifications, referrals


async def fulfill(
    session: AsyncSession,
    org: Org,
    *,
    kind: str,
    credits: int,
    dedupe_key: str,
    plan_key: str | None = None,
    stripe_subscription_id: str | None = None,
    current_period_end: datetime | None = None,
    status: str = "active",
) -> bool:
    """Grant credits for a completed purchase or subscription renewal.

    Records a StripeProcessedEvent keyed on dedupe_key for idempotency; returns
    False immediately (without granting) if the key was already processed.
    Returns True on a successful grant.
    """
    try:
        session.add(StripeProcessedEvent(stripe_event_id=dedupe_key, type=kind))
        await session.flush()
    except sqlalchemy.exc.IntegrityError:
        await session.rollback()
        return False

    if kind == "topup":
        await billing.grant_purchased(
            session,
            org,
            credits,
            reason="purchase",
            stripe_event_id=dedupe_key,
            meta={"kind": "topup"},
        )
    elif kind == "subscription":
        result = await session.exec(
            select(StripeSubscription).where(
                StripeSubscription.stripe_subscription_id == stripe_subscription_id
            )
        )
        sub_row = result.first()

        if sub_row:
            sub_row.plan = plan_key or ""
            sub_row.status = status
            sub_row.credits_per_cycle = credits
            sub_row.current_period_end = current_period_end
            session.add(sub_row)
        else:
            new_sub = StripeSubscription(
                org_id=org.id,
                stripe_subscription_id=stripe_subscription_id or "",
                price_id="",
                plan=plan_key or "",
                status=status,
                credits_per_cycle=credits,
                current_period_end=current_period_end,
            )
            session.add(new_sub)

        await billing.set_subscription_credits(
            session,
            org,
            credits,
            stripe_event_id=dedupe_key,
            meta={"plan_key": plan_key},
        )

    await referrals.on_org_paid(session, org.id)

    reason = (
        "credits_granted_topup" if kind == "topup" else "credits_granted_subscription"
    )
    await notifications.notify_org_members_by_role(
        session,
        org.id,
        NotificationType.BILLING,
        max_access_level=AccessLevel.OWNER,
        payload={"reason": reason, "kind": kind, "credits": credits, "plan": plan_key},
    )

    return True
