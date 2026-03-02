from datetime import UTC, datetime


def get_datetime_utc() -> datetime:
    """Get the current datetime in UTC timezone.

    Returns:
        datetime: The current datetime in UTC timezone.
    """
    return datetime.now(UTC)
