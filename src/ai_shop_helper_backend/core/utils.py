from datetime import UTC, datetime


def get_datetime_utc() -> datetime:
    """Get the current datetime in UTC timezone.

    Returns:
        datetime: The current datetime in UTC timezone.
    """
    return datetime.now(UTC)


def parse_urls(urls: str | list[str]) -> list[str]:
    """Parse a comma-separated string of URLs into a list of strings.

    Returns:
        list[str]: The list of URLs.
    """
    if isinstance(urls, str):
        urls = urls.split(",")
    return [o.strip().rstrip("/") for o in urls if o.strip()]
