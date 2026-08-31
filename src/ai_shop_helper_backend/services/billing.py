import json
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.models.billing import CreditTransaction
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.services.orgs import get_org_by_id

BUCKET_SUBSCRIPTION: Literal["subscription"] = "subscription"
BUCKET_PURCHASED: Literal["purchased"] = "purchased"

REASON_PURCHASE = "purchase"
REASON_SUBSCRIPTION_CYCLE = "subscription_cycle"
REASON_AGENT_RUN = "agent_run"
REASON_ADJUSTMENT = "adjustment"
REASON_REFUND = "refund"
REASON_EXPIRY = "expiry"
REASON_REFERRAL = "referral"


async def get_balance(session: AsyncSession, org_id: UUID) -> Org | None:
    """Return the org (carrying subscription_credits and purchased_credits) or None."""
    return await get_org_by_id(session, org_id)


async def list_ledger(
    session: AsyncSession,
    org_id: UUID,
    offset: int,
    limit: int,
) -> tuple[list[CreditTransaction], int]:
    """Return a page of ledger rows for an org, newest first, plus total count."""
    total_result = await session.exec(
        select(func.count())
        .select_from(CreditTransaction)
        .where(CreditTransaction.org_id == org_id)
    )
    rows_result = await session.exec(
        select(CreditTransaction)
        .where(CreditTransaction.org_id == org_id)
        .order_by(desc(CreditTransaction.created_at))
        .offset(offset)
        .limit(limit)
    )
    return list(rows_result.all()), total_result.one()


async def grant_purchased(
    session: AsyncSession,
    org: Org,
    amount: int,
    reason: str = REASON_PURCHASE,
    stripe_event_id: str | None = None,
    meta: dict | None = None,
) -> CreditTransaction:
    """Increment org.purchased_credits by amount and record a ledger row."""
    org.purchased_credits += amount
    row = _record(
        session,
        org=org,
        amount=amount,
        bucket=BUCKET_PURCHASED,
        balance_after=org.purchased_credits,
        reason=reason,
        stripe_event_id=stripe_event_id,
        meta=meta,
    )
    session.add(org)
    return row


async def set_subscription_credits(
    session: AsyncSession,
    org: Org,
    allotment: int,
    stripe_event_id: str | None = None,
    meta: dict | None = None,
) -> None:
    """Reset org.subscription_credits to allotment for a new billing cycle.

    If credits remain from the prior cycle, an expiry row is written first (stripe_event_id=None).
    The grant row carries the stripe_event_id.
    """
    if org.subscription_credits > 0:
        _record(
            session,
            org=org,
            amount=-org.subscription_credits,
            bucket=BUCKET_SUBSCRIPTION,
            balance_after=0,
            reason=REASON_EXPIRY,
            stripe_event_id=None,
            meta=meta,
        )
    org.subscription_credits = allotment
    _record(
        session,
        org=org,
        amount=allotment,
        bucket=BUCKET_SUBSCRIPTION,
        balance_after=allotment,
        reason=REASON_SUBSCRIPTION_CYCLE,
        stripe_event_id=stripe_event_id,
        meta=meta,
    )
    session.add(org)


async def debit_credits(
    session: AsyncSession,
    org: Org,
    amount: int,
    reason: str = REASON_AGENT_RUN,
    meta: dict | None = None,
) -> tuple[int, int]:
    """Debit credits subscription-first, then purchased.

    Raises HTTPException(402) if total balance is insufficient; org is not mutated in that case.
    Returns the split actually taken from each bucket as (from_subscription, from_purchased) so a
    later refund can restore the original buckets.
    """
    if org.subscription_credits + org.purchased_credits < amount:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    from_sub = min(amount, org.subscription_credits)
    from_pur = amount - from_sub

    if from_sub > 0:
        org.subscription_credits -= from_sub
        _record(
            session,
            org=org,
            amount=-from_sub,
            bucket=BUCKET_SUBSCRIPTION,
            balance_after=org.subscription_credits,
            reason=reason,
            stripe_event_id=None,
            meta=meta,
        )

    if from_pur > 0:
        org.purchased_credits -= from_pur
        _record(
            session,
            org=org,
            amount=-from_pur,
            bucket=BUCKET_PURCHASED,
            balance_after=org.purchased_credits,
            reason=reason,
            stripe_event_id=None,
            meta=meta,
        )

    session.add(org)
    return from_sub, from_pur


async def refund_credits(
    session: AsyncSession,
    org: Org,
    from_sub: int,
    from_pur: int,
    reason: str = REASON_REFUND,
    meta: dict | None = None,
) -> None:
    """Restore a previously-debited split to its original buckets.

    Mirrors debit_credits in reverse: returns from_sub to the subscription bucket and from_pur to
    the purchased bucket, one ledger row per non-zero bucket.
    """
    if from_sub > 0:
        org.subscription_credits += from_sub
        _record(
            session,
            org=org,
            amount=from_sub,
            bucket=BUCKET_SUBSCRIPTION,
            balance_after=org.subscription_credits,
            reason=reason,
            stripe_event_id=None,
            meta=meta,
        )

    if from_pur > 0:
        org.purchased_credits += from_pur
        _record(
            session,
            org=org,
            amount=from_pur,
            bucket=BUCKET_PURCHASED,
            balance_after=org.purchased_credits,
            reason=reason,
            stripe_event_id=None,
            meta=meta,
        )

    session.add(org)


def _record(
    session: AsyncSession,
    org: Org,
    amount: int,
    bucket: str,
    balance_after: int,
    reason: str,
    stripe_event_id: str | None,
    meta: dict | None,
) -> CreditTransaction:
    """Build a CreditTransaction row, add it to the session, and return it."""
    row = CreditTransaction(
        org_id=org.id,
        amount=amount,
        bucket=bucket,
        balance_after=balance_after,
        reason=reason,
        stripe_event_id=stripe_event_id,
        metadata_json=json.dumps(meta) if meta is not None else None,
    )
    session.add(row)
    return row
