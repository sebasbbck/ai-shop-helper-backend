import secrets
from collections.abc import Sequence
from uuid import UUID

from sqlmodel import col, desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.constants import REFERRAL_REWARD
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.referrals import (
    STATUS_CAPPED,
    STATUS_PENDING,
    STATUS_REWARDED,
    Referral,
    ReferralCode,
)
from ai_shop_helper_backend.services import billing, org_users
from ai_shop_helper_backend.services.orgs import get_org_by_id

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 8
_CODE_MAX_ATTEMPTS = 10


def _generate_code() -> str:
    """Build a random shareable referral code with no ambiguous characters."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


async def resolve_code(session: AsyncSession, code: str) -> ReferralCode | None:
    """Return the referral code row for a raw code string, or None."""
    result = await session.exec(select(ReferralCode).where(ReferralCode.code == code))
    return result.first()


async def get_code_by_org(session: AsyncSession, org_id: UUID) -> ReferralCode | None:
    """Return the referral code owned by an org, or None."""
    result = await session.exec(
        select(ReferralCode).where(ReferralCode.org_id == org_id)
    )
    return result.first()


async def _unique_code(session: AsyncSession) -> str:
    """Generate a code that does not yet exist, retrying on collision."""
    for _ in range(_CODE_MAX_ATTEMPTS):
        candidate = _generate_code()
        if await resolve_code(session, candidate) is None:
            return candidate
    raise RuntimeError("could not generate a unique referral code")


async def get_or_create_code(
    session: AsyncSession, org_id: UUID, user_id: UUID
) -> ReferralCode:
    """Return the org's referral code, creating it on first request."""
    existing = await get_code_by_org(session, org_id)
    if existing is not None:
        return existing
    code = ReferralCode(
        org_id=org_id, code=await _unique_code(session), created_by=user_id
    )
    session.add(code)
    return code


async def get_referral_by_referee_user(
    session: AsyncSession, referee_user_id: UUID
) -> Referral | None:
    """Return the referral tied to a referee user, or None."""
    result = await session.exec(
        select(Referral).where(Referral.referee_user_id == referee_user_id)
    )
    return result.first()


async def list_referrals(
    session: AsyncSession, referrer_org_id: UUID
) -> Sequence[Referral]:
    """Return all referrals for a referrer org, newest first."""
    result = await session.exec(
        select(Referral)
        .where(Referral.referrer_org_id == referrer_org_id)
        .order_by(desc(Referral.created_at))
    )
    return result.all()


async def count_rewarded_this_month(
    session: AsyncSession, referrer_org_id: UUID
) -> int:
    """Count referrals rewarded to a referrer org in the current calendar month."""
    month_start = get_datetime_utc().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    result = await session.exec(
        select(func.count())
        .select_from(Referral)
        .where(Referral.referrer_org_id == referrer_org_id)
        .where(Referral.status == STATUS_REWARDED)
        .where(col(Referral.rewarded_at) >= month_start)
    )
    return result.one()


async def record_signup(
    session: AsyncSession, code: str, referee_user_id: UUID
) -> Referral | None:
    """Record a pending referral for a new signup that used a referral code.

    Returns None (a no-op) when the code is unknown or the user is already referred.
    """
    referral_code = await resolve_code(session, code)
    if referral_code is None:
        return None
    if await get_referral_by_referee_user(session, referee_user_id) is not None:
        return None
    referral = Referral(
        referrer_org_id=referral_code.org_id,
        referee_user_id=referee_user_id,
        status=STATUS_PENDING,
    )
    session.add(referral)
    return referral


async def link_referee_org(
    session: AsyncSession, referee_user_id: UUID, org_id: UUID
) -> None:
    """Bind a pending referral to the referee's first org, unless it is self-referral."""
    referral = await get_referral_by_referee_user(session, referee_user_id)
    if referral is None or referral.referee_org_id is not None:
        return
    if referral.referrer_org_id == org_id:
        return
    if (
        await org_users.get_org_user(session, referee_user_id, referral.referrer_org_id)
        is not None
    ):
        return
    referral.referee_org_id = org_id
    session.add(referral)


async def on_org_paid(session: AsyncSession, org_id: UUID) -> Referral | None:
    """Qualify and reward a pending referral once its referee org spends real money.

    Grants referrer/referee credits within the monthly cap; over the cap the referral is
    marked capped without a grant. A no-op when no pending referral targets this org.
    """
    result = await session.exec(
        select(Referral).where(
            Referral.referee_org_id == org_id,
            Referral.status == STATUS_PENDING,
        )
    )
    referral = result.first()
    if referral is None:
        return None

    referral.qualified_at = get_datetime_utc()

    if (
        await count_rewarded_this_month(session, referral.referrer_org_id)
        >= REFERRAL_REWARD.monthly_cap
    ):
        referral.status = STATUS_CAPPED
        session.add(referral)
        return referral

    if REFERRAL_REWARD.referrer_credits > 0:
        referrer_org = await get_org_by_id(session, referral.referrer_org_id)
        if referrer_org is not None:
            await billing.grant_purchased(
                session,
                referrer_org,
                REFERRAL_REWARD.referrer_credits,
                reason=billing.REASON_REFERRAL,
                stripe_event_id=f"ref_{referral.id}_r",
                meta={"referral_id": str(referral.id), "role": "referrer"},
            )

    if REFERRAL_REWARD.referee_credits > 0:
        referee_org = await get_org_by_id(session, org_id)
        if referee_org is not None:
            await billing.grant_purchased(
                session,
                referee_org,
                REFERRAL_REWARD.referee_credits,
                reason=billing.REASON_REFERRAL,
                stripe_event_id=f"ref_{referral.id}_e",
                meta={"referral_id": str(referral.id), "role": "referee"},
            )

    referral.status = STATUS_REWARDED
    referral.rewarded_at = get_datetime_utc()
    referral.referrer_credits = REFERRAL_REWARD.referrer_credits
    referral.referee_credits = REFERRAL_REWARD.referee_credits
    session.add(referral)
    return referral
