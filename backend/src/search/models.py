"""Typed models for deterministic web search planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.core.time_context import DEFAULT_TIMEZONE

TemporalScope = Literal["none", "today", "yesterday", "recent", "this_week", "latest", "explicit"]
FreshnessStatus = Literal["not_required", "fresh", "stale", "unknown"]


@dataclass(frozen=True)
class TemporalConstraint:
    """Resolved time constraint from a user query."""

    scope: TemporalScope = "none"
    date_from: str | None = None
    date_to: str | None = None
    timezone: str = DEFAULT_TIMEZONE
    freshness_required: bool = False
    phrase: str = ""

    @property
    def exact_date(self) -> str | None:
        """Return the exact date when the constraint covers one day."""
        if self.date_from and self.date_from == self.date_to:
            return self.date_from
        return None

    def as_dict(self) -> dict:
        """Return a JSON-safe representation."""
        return {
            "scope": self.scope,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "timezone": self.timezone,
            "freshness_required": self.freshness_required,
            "phrase": self.phrase,
        }


@dataclass(frozen=True)
class ContentTypeProfile:
    """Search profile for one type of content inside a source."""

    id: str
    aliases: tuple[str, ...]
    search_terms: tuple[str, ...]
    date_url_template: str | None = None


@dataclass(frozen=True)
class SourceProfile:
    """Searchable source metadata kept out of planning logic."""

    id: str
    canonical_name: str
    aliases: tuple[str, ...]
    site: str
    content_types: dict[str, ContentTypeProfile] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchIntent:
    """Structured search intent inferred from a user query."""

    original_query: str
    temporal: TemporalConstraint
    source: SourceProfile | None = None
    content_type: ContentTypeProfile | None = None

    @property
    def freshness_required(self) -> bool:
        """Return whether the answer needs fresh/current evidence."""
        return self.temporal.freshness_required


@dataclass(frozen=True)
class SearchQueryPlan:
    """Executable web search query plan."""

    original_query: str
    queries: list[str]
    temporal: TemporalConstraint
    source_id: str | None = None
    source_name: str | None = None
    site: str | None = None
    content_type: str | None = None
    date_url: str | None = None
    max_queries: int = 2

    @property
    def primary_query(self) -> str:
        """Return the first executable query or the original query."""
        return self.queries[0] if self.queries else self.original_query

    @property
    def freshness_required(self) -> bool:
        """Return whether result freshness should be checked."""
        return self.temporal.freshness_required

    def as_dict(self) -> dict:
        """Return a JSON-safe representation."""
        return {
            "original_query": self.original_query,
            "queries": list(self.queries),
            "temporal": self.temporal.as_dict(),
            "source_id": self.source_id,
            "source_name": self.source_name,
            "site": self.site,
            "content_type": self.content_type,
            "date_url": self.date_url,
            "max_queries": self.max_queries,
        }


@dataclass(frozen=True)
class EvidenceDateValidation:
    """Freshness validation for formatted web search evidence."""

    status: FreshnessStatus
    expected_date: str | None = None
    observed_dates: list[str] = field(default_factory=list)
    latest_observed_date: str | None = None
    warning: str | None = None

    def as_dict(self) -> dict:
        """Return a JSON-safe representation."""
        return {
            "status": self.status,
            "expected_date": self.expected_date,
            "observed_dates": list(self.observed_dates),
            "latest_observed_date": self.latest_observed_date,
            "warning": self.warning,
        }
