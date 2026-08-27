from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel


class ReferralRewardPublic(SQLModel):
    """Public view of the configured referral reward."""

    referrer_credits: int
    referee_credits: int
    monthly_cap: int


class ReferralPublic(SQLModel):
    """Public view of a single referral row."""

    id: UUID
    status: str
    referee_org_id: UUID | None
    qualified_at: datetime | None
    rewarded_at: datetime | None
    referrer_credits: int | None
    referee_credits: int | None
    created_at: datetime


class ReferralOverview(SQLModel):
    """Referral dashboard payload for an organisation."""

    code: str
    share_url: str
    reward: ReferralRewardPublic
    rewarded_this_month: int
    referrals: list[ReferralPublic]


class ReferrerInfo(SQLModel):
    """Public info shown to a referee landing on the signup page via a code."""

    org_name: str
    referee_credits: int
