from dataclasses import dataclass


class AccessLevel:
    """Access level constants for role-based authorization."""

    OWNER = 0
    ADMIN = 10
    MEMBER = 50
    VIEWER = 100


CURRENCY = "eur"
FREE_TIER_CREDITS = 50

TOPUP_LOOKUP_KEY = "aish_topup"
TOPUP_MIN_AMOUNT = 500
TOPUP_MAX_AMOUNT = 50000
TOPUP_CENTS_PER_CREDIT = 10


@dataclass(frozen=True)
class SubscriptionTier:
    """Describes one recurring subscription credit tier."""

    key: str
    name: str
    credits: int
    unit_amount: int


SUBSCRIPTION_TIERS: list[SubscriptionTier] = [
    SubscriptionTier("starter", "Starter", 500, 1900),
    SubscriptionTier("pro", "Pro", 2000, 5900),
]

SUB_BY_KEY: dict[str, SubscriptionTier] = {t.key: t for t in SUBSCRIPTION_TIERS}


def stripe_lookup_key(key: str) -> str:
    """Return the Stripe lookup key for a tier key."""
    return f"aish_{key}"


def credits_for_topup(amount_cents: int) -> int:
    """Return credits granted for a top-up of the given amount in cents."""
    return amount_cents // TOPUP_CENTS_PER_CREDIT
