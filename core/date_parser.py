import re
from datetime import datetime, timedelta
from typing import Optional


def parse_relative_date(text: str) -> Optional[datetime]:
    """
    Parse relative date strings like:
        'Posted 12 hours ago'
        'Posted a day ago'
        'Posted 2 days ago'
        'Posted 30+ days ago'
        'Posted a month ago'

    Returns a datetime object representing the approximate posting date,
    or None if the text cannot be parsed.
    """
    if not text:
        return None

    text = text.strip().lower()

    # Try to extract the relative part
    # Patterns: "posted X ago", "X ago", etc.
    match = re.search(
        r"(\d+\+?|a|an)\s+(second|minute|hour|day|week|month|year)s?\s+ago",
        text,
    )

    if not match:
        return None

    quantity_str = match.group(1)
    unit = match.group(2)

    # Parse quantity
    if quantity_str in ("a", "an"):
        quantity = 1
    else:
        quantity = int(quantity_str.rstrip("+"))

    # Build timedelta
    now = datetime.now()
    if unit == "second":
        return now - timedelta(seconds=quantity)
    elif unit == "minute":
        return now - timedelta(minutes=quantity)
    elif unit == "hour":
        return now - timedelta(hours=quantity)
    elif unit == "day":
        return now - timedelta(days=quantity)
    elif unit == "week":
        return now - timedelta(weeks=quantity)
    elif unit == "month":
        return now - timedelta(days=quantity * 30)  # Approximate
    elif unit == "year":
        return now - timedelta(days=quantity * 365)  # Approximate

    return None


def parse_absolute_date(text: str, fmt: str) -> Optional[datetime]:
    """
    Parse absolute date strings using a strftime format.
    Example: parse_absolute_date("Apr 26, 2026", "%b %d, %Y")

    Returns a datetime object, or None if parsing fails.
    """
    if not text:
        return None

    text = text.strip()

    try:
        return datetime.strptime(text, fmt)
    except ValueError:
        return None


def is_within_days(posted_date: Optional[datetime], max_days: int) -> bool:
    """Check if a job's posted date is within the last `max_days` days."""
    if posted_date is None:
        # If we can't determine the date, include it to be safe
        return True

    cutoff = datetime.now() - timedelta(days=max_days)
    return posted_date >= cutoff
