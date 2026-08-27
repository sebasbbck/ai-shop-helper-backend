import logging

import stripe
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.constants import (
    CURRENCY,
    SUBSCRIPTION_TIERS,
    TOPUP_LOOKUP_KEY,
    TOPUP_MAX_AMOUNT,
    TOPUP_MIN_AMOUNT,
    stripe_lookup_key,
)
from ai_shop_helper_backend.models.billing import StripeCustomer
from ai_shop_helper_backend.models.orgs import Org

stripe.api_key = settings.STRIPE_SECRET_KEY

_price_id_cache: dict[str, str] = {}

logger = logging.getLogger(__name__)


async def ensure_customer(session: AsyncSession, org: Org) -> str:
    """Return the Stripe customer id for the org, creating one if absent."""
    result = await session.exec(
        select(StripeCustomer).where(StripeCustomer.org_id == org.id)
    )
    existing = result.first()
    if existing:
        return existing.stripe_customer_id

    cust = await stripe.Customer.create_async(
        name=org.name,
        metadata={"org_id": str(org.id)},
    )
    row = StripeCustomer(org_id=org.id, stripe_customer_id=cust.id)
    session.add(row)
    await session.flush()
    return cust.id


async def get_price_id(lookup_key: str) -> str:
    """Return the Stripe price id for a lookup key, memoising the result."""
    if lookup_key in _price_id_cache:
        return _price_id_cache[lookup_key]

    prices = await stripe.Price.list_async(lookup_keys=[lookup_key], limit=1)
    if not prices.data:
        raise HTTPException(
            status_code=500,
            detail=f"Stripe price not seeded: {lookup_key}",
        )

    _price_id_cache[lookup_key] = prices.data[0].id
    return prices.data[0].id


async def create_checkout_session(
    session: AsyncSession,
    org: Org,
    *,
    lookup_key: str,
    mode: str,
    metadata: dict,
) -> str:
    """Create a Stripe Checkout session and return the redirect URL."""
    customer_id = await ensure_customer(session, org)
    price_id = await get_price_id(lookup_key)

    args: dict = {
        "customer": customer_id,
        "mode": mode,
        "line_items": [{"price": price_id, "quantity": 1}],
        "metadata": metadata,
        "success_url": settings.billing_success_url,
        "cancel_url": settings.billing_cancel_url,
    }

    if mode == "subscription":
        args["subscription_data"] = {"metadata": metadata}

    cs = await stripe.checkout.Session.create_async(**args)
    if cs.url is None:
        raise HTTPException(
            status_code=502, detail="Stripe did not return a checkout URL"
        )
    return cs.url


async def create_portal_session(session: AsyncSession, org: Org) -> str:
    """Create a Stripe Billing Portal session and return the redirect URL."""
    customer_id = await ensure_customer(session, org)
    ps = await stripe.billing_portal.Session.create_async(
        customer=customer_id,
        return_url=settings.stripe_portal_return_url,
    )
    if ps.url is None:
        raise HTTPException(
            status_code=502, detail="Stripe did not return a portal URL"
        )
    return ps.url


async def retrieve_checkout_session(session_id: str) -> stripe.checkout.Session:
    """Retrieve a Stripe Checkout session by id, 404 if Stripe rejects it."""
    try:
        return await stripe.checkout.Session.retrieve_async(session_id)
    except stripe.StripeError:
        raise HTTPException(status_code=404, detail="Checkout session not found")


def construct_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify a Stripe webhook signature and return the parsed event."""
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )


async def seed_products() -> None:
    """Ensure subscription and top-up products exist in Stripe (best-effort, startup-safe)."""
    try:
        for t in SUBSCRIPTION_TIERS:
            lookup = stripe_lookup_key(t.key)
            metadata = {
                "plan_key": t.key,
                "kind": "subscription",
                "credits": str(t.credits),
            }
            existing = await stripe.Price.list_async(lookup_keys=[lookup], limit=1)
            current = existing.data[0] if existing.data else None

            if current is not None and current.unit_amount == t.unit_amount:
                continue

            if current is None:
                product = await stripe.Product.create_async(
                    name=f"AI Shop Helper — {t.name}",
                    metadata=metadata,
                )
                product_id = product.id
            else:
                product_id = current.product

            price_args: dict = {
                "product": product_id,
                "currency": CURRENCY,
                "unit_amount": t.unit_amount,
                "recurring": {"interval": "month"},
                "lookup_key": lookup,
                "metadata": metadata,
            }
            if current is not None:
                price_args["transfer_lookup_key"] = True

            await stripe.Price.create_async(**price_args)

            if current is not None:
                await stripe.Price.modify_async(current.id, active=False)

        topup_existing = await stripe.Price.list_async(
            lookup_keys=[TOPUP_LOOKUP_KEY], limit=1
        )
        if not topup_existing.data:
            topup_product = await stripe.Product.create_async(
                name="AI Shop Helper — Credit top-up",
                metadata={"kind": "topup"},
            )
            await stripe.Price.create_async(
                product=topup_product.id,
                currency=CURRENCY,
                custom_unit_amount={
                    "enabled": True,
                    "minimum": TOPUP_MIN_AMOUNT,
                    "maximum": TOPUP_MAX_AMOUNT,
                },
                lookup_key=TOPUP_LOOKUP_KEY,
                metadata={"kind": "topup"},
            )

    except Exception:
        logger.warning(
            "seed_products: Stripe seeding failed (non-fatal)", exc_info=True
        )
