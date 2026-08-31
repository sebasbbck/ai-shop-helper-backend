import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import TimestampMixin, UUIDMixin

STATUS_PENDING = "pending"
STATUS_REWARDED = "rewarded"
STATUS_CAPPED = "capped"


class ReferralCode(UUIDMixin, TimestampMixin, SQLModel, table=True):
    """One shareable referral code per organisation (reward target)."""

    __tablename__ = "referralcode"
    __table_args__ = (UniqueConstraint("org_id", name="uq_referralcode_org"),)

    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    code: str = Field(max_length=16, unique=True, index=True)
    created_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True
    )


class Referral(UUIDMixin, TimestampMixin, SQLModel, table=True):
    """One row per referred signup, tracked from pending to rewarded/capped."""

    __tablename__ = "referral"
    __table_args__ = (
        UniqueConstraint("referee_user_id", name="uq_referral_referee_user"),
    )

    referrer_org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    referee_user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    referee_org_id: uuid.UUID | None = Field(
        default=None, foreign_key="org.id", index=True, nullable=True
    )
    status: str = Field(default=STATUS_PENDING, max_length=32)
    qualified_at: datetime | None = Field(default=None)
    rewarded_at: datetime | None = Field(default=None)
    referrer_credits: int | None = Field(default=None)
    referee_credits: int | None = Field(default=None)
