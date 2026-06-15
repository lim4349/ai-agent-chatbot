"""Deterministic temporal expression resolver for web search."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, timedelta

from src.core.time_context import DEFAULT_TIMEZONE, current_datetime
from src.search.models import TemporalConstraint

ISO_DATE_RE = re.compile(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b")


class TemporalResolver:
    """Resolve common time expressions without relying on the LLM."""

    def __init__(
        self,
        *,
        timezone: str = DEFAULT_TIMEZONE,
        today_provider: Callable[[], date] | None = None,
    ) -> None:
        self.timezone = timezone
        self.today_provider = today_provider

    def resolve(self, query: str) -> TemporalConstraint:
        """Resolve a temporal constraint from a user query."""
        lowered = query.lower()
        today = self.today()

        explicit_date = self.extract_explicit_date(query)
        if explicit_date:
            return TemporalConstraint(
                scope="explicit",
                date_from=explicit_date,
                date_to=explicit_date,
                timezone=self.timezone,
                freshness_required=True,
                phrase=explicit_date,
            )

        if self.contains_any(lowered, ("오늘", "금일", "today")):
            today_iso = today.isoformat()
            return TemporalConstraint(
                scope="today",
                date_from=today_iso,
                date_to=today_iso,
                timezone=self.timezone,
                freshness_required=True,
                phrase="today",
            )

        if self.contains_any(lowered, ("어제", "yesterday")):
            yesterday = today - timedelta(days=1)
            yesterday_iso = yesterday.isoformat()
            return TemporalConstraint(
                scope="yesterday",
                date_from=yesterday_iso,
                date_to=yesterday_iso,
                timezone=self.timezone,
                freshness_required=True,
                phrase="yesterday",
            )

        if self.contains_any(lowered, ("이번 주", "이번주", "this week")):
            week_start = today - timedelta(days=today.weekday())
            return TemporalConstraint(
                scope="this_week",
                date_from=week_start.isoformat(),
                date_to=today.isoformat(),
                timezone=self.timezone,
                freshness_required=True,
                phrase="this week",
            )

        if self.contains_any(lowered, ("최근", "recent")):
            return TemporalConstraint(
                scope="recent",
                date_from=(today - timedelta(days=7)).isoformat(),
                date_to=today.isoformat(),
                timezone=self.timezone,
                freshness_required=True,
                phrase="recent",
            )

        if self.contains_any(lowered, ("최신", "현재", "지금", "latest", "current", "now")):
            return TemporalConstraint(
                scope="latest",
                date_to=today.isoformat(),
                timezone=self.timezone,
                freshness_required=True,
                phrase="latest",
            )

        return TemporalConstraint(timezone=self.timezone)

    def today(self) -> date:
        """Return today's date in the configured timezone."""
        if self.today_provider:
            return self.today_provider()
        return current_datetime(self.timezone).date()

    def extract_explicit_date(self, query: str) -> str | None:
        """Extract an explicit YYYY-MM-DD style date."""
        match = ISO_DATE_RE.search(query)
        if not match:
            return None
        year, month, day = match.groups()
        return date(int(year), int(month), int(day)).isoformat()

    def contains_any(self, text: str, terms: tuple[str, ...]) -> bool:
        """Return whether any temporal term appears in text."""
        return any(term in text for term in terms)
