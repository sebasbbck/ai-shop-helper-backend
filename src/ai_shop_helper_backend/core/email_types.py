from enum import Enum

SUPPORTED_LOCALES = ("en", "es")
DEFAULT_LOCALE = "es"


def notifuse_language(locale: str) -> str:
    """Map app locale to the Notifuse contact language.

    Notifuse template variants + workspace languages use short codes (en/es),
    so pass the short code through; fall back to the default when unknown.
    """
    return locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE


class EmailType(str, Enum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "password_reset"


REQUIRED_NOTIFICATION_IDS = [e.value for e in EmailType]
