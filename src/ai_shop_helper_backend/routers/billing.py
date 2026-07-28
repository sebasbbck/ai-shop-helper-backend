from uuid import UUID

import stripe
from fastapi import APIRouter, HTTPException, Request, status

from ai_shop_helper_backend.core.constants import (
    CURRENCY,
    FREE_TIER_CREDITS,
    SUB_BY_KEY,
    TOPUP_CENTS_PER_CREDIT,
    TOPUP_LOOKUP_KEY,
    TOPUP_MAX_AMOUNT,
    TOPUP_MIN_AMOUNT,
    credits_for_topup,
    stripe_lookup_key,
)
from ai_shop_helper_backend.core.deps import (
    CurrentOrgAdmin,
    CurrentOrgMember,
    CurrentUser,
    PaginationDep,
    SessionDep,
)
from ai_shop_helper_backend.schemas.billing import (
    BalanceResponse,
    CatalogResponse,
    CheckoutConfirm,
    CheckoutCreate,
    CreditPlanPublic,
    LedgerEntryPublic,
    TopupConfigPublic,
    UrlResponse,
)
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.services import billing, billing_webhook
from ai_shop_helper_backend.services import billing_fulfillment as fulfillment
from ai_shop_helper_backend.services import stripe_gateway as gateway
from ai_shop_helper_backend.services.orgs import get_org_by_id

org_router = APIRouter(prefix="/orgs/{org_id}/billing", tags=["billing"])
catalog_router = APIRouter(prefix="/billing", tags=["billing"])


@org_router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    org_id: UUID,
    org_member: CurrentOrgMember,
    session: SessionDep,
) -> BalanceResponse:
    """Return the credit balance for an organisation."""
    org = await get_org_by_id(session, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return BalanceResponse(
        subscription_credits=org.subscription_credits,
        purchased_credits=org.purchased_credits,
        total=org.subscription_credits + org.purchased_credits,
    )


@org_router.get("/ledger", response_model=PaginatedResponse[LedgerEntryPublic])
async def get_ledger(
    org_id: UUID,
    org_member: CurrentOrgMember,
    pagination: PaginationDep,
    session: SessionDep,
) -> PaginatedResponse[LedgerEntryPublic]:
    """Return paginated credit-ledger entries for an organisation, newest first."""
    rows, total = await billing.list_ledger(
        session, org_id, pagination.offset, pagination.limit
    )
    return PaginatedResponse(
        items=[LedgerEntryPublic.model_validate(r) for r in rows],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@org_router.post("/checkout", response_model=UrlResponse)
async def create_checkout(
    org_id: UUID,
    body: CheckoutCreate,
    org_admin: CurrentOrgAdmin,
    session: SessionDep,
) -> UrlResponse:
    """Create a Stripe Checkout session for the requested plan."""
    if body.plan_key == "topup":
        lookup_key = TOPUP_LOOKUP_KEY
        mode = "payment"
        metadata: dict = {"org_id": str(org_id), "kind": "topup"}
    elif body.plan_key in SUB_BY_KEY:
        lookup_key = stripe_lookup_key(body.plan_key)
        mode = "subscription"
        metadata = {
            "org_id": str(org_id),
            "plan_key": body.plan_key,
            "kind": "subscription",
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown plan_key: {body.plan_key}",
        )
    org = await get_org_by_id(session, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    url = await gateway.create_checkout_session(
        session, org, lookup_key=lookup_key, mode=mode, metadata=metadata
    )
    return UrlResponse(url=url)


@org_router.post("/checkout/confirm", response_model=BalanceResponse)
async def confirm_checkout(
    org_id: UUID,
    body: CheckoutConfirm,
    org_member: CurrentOrgMember,
    session: SessionDep,
) -> BalanceResponse:
    """Confirm a completed Stripe Checkout session and grant the purchased credits."""
    cs = await gateway.retrieve_checkout_session(body.session_id)
    metadata = cs.metadata.to_dict() if cs.metadata else {}

    if metadata.get("org_id") != str(org_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checkout session does not belong to this organization",
        )

    if cs.payment_status != "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment not completed",
        )

    org = await get_org_by_id(session, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    kind = metadata["kind"]
    sid = body.session_id

    if kind == "topup":
        credits = credits_for_topup(cs.amount_total or 0)
        await fulfillment.fulfill(
            session,
            org,
            kind="topup",
            credits=credits,
            dedupe_key=f"cs_{sid}",
        )
    elif kind == "subscription":
        plan_key = metadata["plan_key"]
        credits = SUB_BY_KEY[plan_key].credits
        await fulfillment.fulfill(
            session,
            org,
            kind="subscription",
            credits=credits,
            plan_key=plan_key,
            stripe_subscription_id=getattr(cs, "subscription", None),
            dedupe_key=f"cs_{sid}",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown kind in session metadata: {kind}",
        )

    refreshed = await get_org_by_id(session, org_id)
    if refreshed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return BalanceResponse(
        subscription_credits=refreshed.subscription_credits,
        purchased_credits=refreshed.purchased_credits,
        total=refreshed.subscription_credits + refreshed.purchased_credits,
    )


@org_router.post("/portal", response_model=UrlResponse)
async def create_portal(
    org_id: UUID,
    org_admin: CurrentOrgAdmin,
    session: SessionDep,
) -> UrlResponse:
    """Create a Stripe Billing Portal session for the organisation."""
    org = await get_org_by_id(session, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    url = await gateway.create_portal_session(session, org)
    return UrlResponse(url=url)


@catalog_router.post("/webhook")
async def stripe_webhook(request: Request, session: SessionDep) -> dict[str, bool]:
    """Receive and process Stripe webhook events (signature-verified, no auth)."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = gateway.construct_event(payload, sig)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid signature")
    await billing_webhook.handle_event(session, event)
    return {"received": True}


@catalog_router.get("/catalog", response_model=CatalogResponse)
async def get_catalog(
    current_user: CurrentUser,
) -> CatalogResponse:
    """Return the billing catalog."""
    return CatalogResponse(
        free_credits=FREE_TIER_CREDITS,
        plans=[
            CreditPlanPublic(
                key=t.key,
                name=t.name,
                credits=t.credits,
                unit_amount=t.unit_amount,
                currency=CURRENCY,
            )
            for t in SUB_BY_KEY.values()
        ],
        topup=TopupConfigPublic(
            currency=CURRENCY,
            min_amount=TOPUP_MIN_AMOUNT,
            max_amount=TOPUP_MAX_AMOUNT,
            cents_per_credit=TOPUP_CENTS_PER_CREDIT,
        ),
    )
