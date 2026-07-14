from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel


class BalanceResponse(SQLModel):
    """Credit balance for an organisation."""

    subscription_credits: int
    purchased_credits: int
    total: int


class LedgerEntryPublic(SQLModel):
    """Public view of a single credit-ledger row."""

    id: UUID
    amount: int
    bucket: str
    balance_after: int
    reason: str
    created_at: datetime


class CreditPlanPublic(SQLModel):
    """Public catalogue entry for a subscription plan."""

    key: str
    name: str
    credits: int
    unit_amount: int
    currency: str


class TopupConfigPublic(SQLModel):
    """Public configuration for the credit top-up product."""

    currency: str
    min_amount: int
    max_amount: int
    cents_per_credit: int


class CatalogResponse(SQLModel):
    """Full billing catalog response."""

    free_credits: int
    plans: list[CreditPlanPublic]
    topup: TopupConfigPublic


class CheckoutCreate(SQLModel):
    """Request body for initiating a Stripe Checkout session."""

    plan_key: str


class CheckoutConfirm(SQLModel):
    """Request body for confirming a completed Stripe Checkout session."""

    session_id: str


class UrlResponse(SQLModel):
    """Response carrying a redirect URL."""

    url: str
