from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import (
    CreatedAtMixin,
    TimestampMixin,
    UUIDMixin,
)


class CreditTransaction(UUIDMixin, CreatedAtMixin, SQLModel, table=True):
    """Append-only ledger recording every credit mutation for an org."""

    __tablename__ = "credittransaction"

    org_id: UUID = Field(foreign_key="org.id", index=True)
    amount: int
    bucket: str = Field(max_length=64)
    balance_after: int
    reason: str = Field(max_length=64)
    stripe_event_id: str | None = Field(default=None, max_length=255, unique=True)
    metadata_json: str | None = Field(default=None, max_length=4096)


class StripeCustomer(UUIDMixin, CreatedAtMixin, SQLModel, table=True):
    """Maps one Stripe customer to one org."""

    __tablename__ = "stripecustomer"
    __table_args__ = (UniqueConstraint("org_id"),)

    org_id: UUID = Field(foreign_key="org.id", index=True)
    stripe_customer_id: str = Field(max_length=255, unique=True, index=True)


class StripeProcessedEvent(UUIDMixin, CreatedAtMixin, SQLModel, table=True):
    """Records processed Stripe webhook event ids for idempotency."""

    __tablename__ = "stripeprocessedevent"

    stripe_event_id: str = Field(max_length=255, unique=True, index=True)
    type: str = Field(max_length=255)


class StripeSubscription(UUIDMixin, TimestampMixin, SQLModel, table=True):
    """Mirrors the active Stripe subscription for an org."""

    __tablename__ = "stripesubscription"

    org_id: UUID = Field(foreign_key="org.id", index=True)
    stripe_subscription_id: str = Field(max_length=255, unique=True, index=True)
    price_id: str = Field(max_length=255)
    plan: str = Field(max_length=64)
    status: str = Field(max_length=64)
    credits_per_cycle: int
    current_period_end: datetime | None = Field(default=None)
