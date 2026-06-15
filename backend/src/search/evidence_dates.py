"""Freshness validation for formatted web search evidence."""

from __future__ import annotations

import re
from datetime import date

from src.search.models import EvidenceDateValidation, SearchQueryPlan

DATE_RE = re.compile(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b")


class EvidenceDateValidator:
    """Validate whether web evidence satisfies a temporal search plan."""

    def validate_text(self, text: str, plan: SearchQueryPlan) -> EvidenceDateValidation:
        """Validate dates found in formatted search text against the plan."""
        expected = plan.temporal.exact_date
        if not plan.freshness_required:
            return EvidenceDateValidation(status="not_required")
        if not text.strip():
            return EvidenceDateValidation(status="unknown", expected_date=expected)

        observed_dates = extract_dates(text)
        latest = latest_date(observed_dates)
        if expected:
            if expected in observed_dates:
                return EvidenceDateValidation(
                    status="fresh",
                    expected_date=expected,
                    observed_dates=observed_dates,
                    latest_observed_date=latest,
                )
            if observed_dates:
                return EvidenceDateValidation(
                    status="stale",
                    expected_date=expected,
                    observed_dates=observed_dates,
                    latest_observed_date=latest,
                    warning=(
                        f"Requested evidence for {expected}, but matched web evidence appears "
                        f"to reference {latest or ', '.join(observed_dates)}. Do not claim it is "
                        "today's result."
                    ),
                )

        return EvidenceDateValidation(
            status="unknown",
            expected_date=expected,
            observed_dates=observed_dates,
            latest_observed_date=latest,
            warning=(
                "The user requested current or date-specific evidence, but the web evidence date "
                "could not be verified. State this limitation instead of implying freshness."
            ),
        )


def extract_dates(text: str) -> list[str]:
    """Extract ISO-like dates from URLs or snippets."""
    dates = []
    for year, month, day in DATE_RE.findall(text):
        try:
            parsed = date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            continue
        if parsed not in dates:
            dates.append(parsed)
    return dates


def latest_date(dates: list[str]) -> str | None:
    """Return the latest valid ISO date from a list."""
    if not dates:
        return None
    return max(dates)
