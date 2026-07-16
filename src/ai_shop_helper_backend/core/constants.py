from dataclasses import dataclass


class AccessLevel:
    """Access level constants for role-based authorization."""

    OWNER = 0
    ADMIN = 10
    MEMBER = 50
    VIEWER = 100


CURRENCY = "eur"
FREE_TIER_CREDITS = 50


@dataclass(frozen=True)
class ProjectContextField:
    """A project-level context field, shared by every agent run on the project."""

    key: str
    input_type: str
    required: bool
    label_i18n_key: str


PROJECT_CONTEXT_FIELDS: list[ProjectContextField] = [
    ProjectContextField("business", "textarea", True, "ProjectContext.business.label"),
    ProjectContextField("audience", "textarea", True, "ProjectContext.audience.label"),
]

PROJECT_CONTEXT_KEYS = {f.key for f in PROJECT_CONTEXT_FIELDS}

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


class NotificationType:
    """Notification type constants. Add new types here — no migration required."""

    BILLING = "billing"
    EXECUTION_FINISHED = "execution_finished"
    SERVICE_CHANGE = "service_change"
    USER_STATUS_CHANGE = "user_status_change"


MUTABLE_NOTIFICATION_TYPES: frozenset[str] = frozenset(
    {
        NotificationType.EXECUTION_FINISHED,
        NotificationType.SERVICE_CHANGE,
        NotificationType.USER_STATUS_CHANGE,
    }
)
"""Notification types users may mute. Types left out (e.g. BILLING) are always delivered."""
