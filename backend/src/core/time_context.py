"""Runtime date context for time-sensitive assistant answers."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Seoul"


def current_datetime(timezone: str = DEFAULT_TIMEZONE) -> datetime:
    """Return the current timezone-aware datetime for product prompts."""
    return datetime.now(tz=ZoneInfo(timezone))


def current_date_iso(timezone: str = DEFAULT_TIMEZONE) -> str:
    """Return today's date as YYYY-MM-DD in the product timezone."""
    return current_datetime(timezone).date().isoformat()


def current_date_context(timezone: str = DEFAULT_TIMEZONE) -> str:
    """Return a compact date context string for LLM prompts."""
    return f"Current date: {current_date_iso(timezone)} ({timezone})."
