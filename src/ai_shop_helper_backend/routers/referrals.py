from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.constants import REFERRAL_REWARD
from ai_shop_helper_backend.core.deps import CurrentOrgMember, SessionDep
from ai_shop_helper_backend.schemas.referrals import (
    ReferralOverview,
    ReferralPublic,
    ReferralRewardPublic,
    ReferrerInfo,
)
from ai_shop_helper_backend.services import referrals
from ai_shop_helper_backend.services.orgs import get_org_by_id

org_router = APIRouter(prefix="/orgs/{org_id}/referral", tags=["referrals"])
public_router = APIRouter(prefix="/referral", tags=["referrals"])


def _share_url(code: str) -> str:
    """Build the shareable signup link for a referral code."""
    return f"{settings.FRONTEND_URL.rstrip('/')}/register?ref={code}"


def _reward_public() -> ReferralRewardPublic:
    """Return the configured referral reward as a public payload."""
    return ReferralRewardPublic(
        referrer_credits=REFERRAL_REWARD.referrer_credits,
        referee_credits=REFERRAL_REWARD.referee_credits,
        monthly_cap=REFERRAL_REWARD.monthly_cap,
    )


@org_router.get("", response_model=ReferralOverview)
async def get_referral_overview(
    org_id: UUID,
    org_member: CurrentOrgMember,
    session: SessionDep,
) -> ReferralOverview:
    """Return the referral dashboard for an org, creating its code on first view."""
    current_user, _ = org_member
    code = await referrals.get_or_create_code(session, org_id, current_user.id)
    await session.commit()
    await session.refresh(code)

    rewarded = await referrals.count_rewarded_this_month(session, org_id)
    rows = await referrals.list_referrals(session, org_id)
    return ReferralOverview(
        code=code.code,
        share_url=_share_url(code.code),
        reward=_reward_public(),
        rewarded_this_month=rewarded,
        referrals=[ReferralPublic.model_validate(r) for r in rows],
    )


@public_router.get("/{code}", response_model=ReferrerInfo)
async def get_referrer_info(code: str, session: SessionDep) -> ReferrerInfo:
    """Return the referrer org name for a code so the signup page can greet the referee."""
    referral_code = await referrals.resolve_code(session, code)
    if referral_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Referral code not found"
        )
    org = await get_org_by_id(session, referral_code.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Referral code not found"
        )
    return ReferrerInfo(
        org_name=org.name, referee_credits=REFERRAL_REWARD.referee_credits
    )
