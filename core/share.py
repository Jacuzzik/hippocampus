"""Password links for one note. They expire 60 minutes after they are made, by default.

Links are made on the user's account (core/account.py) and open on the website, where the password is
checked on the server. Signed out, making a link is refused with "Not set up"; the checks still run first.
"""

from datetime import datetime, timedelta

from core.memory import NotSetUp

DEFAULT_MINUTES = 60
MIN_PASSWORD = 8
NOT_SET_UP = "Share links need an account. Sign in under Settings > Account."


def expiry(password: str, minutes: int = DEFAULT_MINUTES, now: datetime | None = None) -> datetime:
    """Check a link's password and length of life, and return when it would expire."""
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"the password must be at least {MIN_PASSWORD} characters")
    if not 1 <= minutes <= 24 * 60:
        raise ValueError("a link lasts from 1 minute to 24 hours")
    start = now or datetime.now().astimezone()
    return start + timedelta(minutes=minutes)


def request_link(password: str, minutes: int = DEFAULT_MINUTES) -> None:
    expiry(password, minutes)
    raise NotSetUp(NOT_SET_UP)
