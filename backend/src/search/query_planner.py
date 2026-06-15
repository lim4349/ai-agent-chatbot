"""Generalized web search query planner."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from src.core.time_context import DEFAULT_TIMEZONE
from src.search.models import SearchIntent, SearchQueryPlan
from src.search.source_profiles import ContentIntentResolver, SourceResolver
from src.search.temporal import TemporalResolver


class SearchQueryPlanner:
    """Turn a user query into one or more executable web search queries."""

    def __init__(
        self,
        *,
        timezone: str = DEFAULT_TIMEZONE,
        today_provider: Callable[[], date] | None = None,
        source_resolver: SourceResolver | None = None,
        content_resolver: ContentIntentResolver | None = None,
    ) -> None:
        self.temporal_resolver = TemporalResolver(
            timezone=timezone,
            today_provider=today_provider,
        )
        self.source_resolver = source_resolver or SourceResolver()
        self.content_resolver = content_resolver or ContentIntentResolver()

    def plan(self, query: str) -> SearchQueryPlan:
        """Build a search query plan for a user query."""
        original_query = query.strip()
        temporal = self.temporal_resolver.resolve(original_query)
        source = self.source_resolver.resolve(original_query)
        content_type = self.content_resolver.resolve(original_query, source)
        intent = SearchIntent(
            original_query=original_query,
            temporal=temporal,
            source=source,
            content_type=content_type,
        )

        queries = self.build_queries(intent)
        date_url = self.build_date_url(intent)
        return SearchQueryPlan(
            original_query=original_query,
            queries=queries,
            temporal=temporal,
            source_id=source.id if source else None,
            source_name=source.canonical_name if source else None,
            site=source.site if source else None,
            content_type=content_type.id if content_type else None,
            date_url=date_url,
            direct_fetch_extractor=(
                content_type.direct_fetch_extractor if content_type else None
            ),
            max_queries=2 if len(queries) > 1 else 1,
        )

    def build_queries(self, intent: SearchIntent) -> list[str]:
        """Build ordered search queries from structured intent."""
        queries = []
        date_url_query = self.build_date_url_query(intent)
        if date_url_query:
            queries.append(date_url_query)

        scoped_query = self.build_scoped_query(intent)
        if scoped_query:
            queries.append(scoped_query)

        broad_query = self.build_broad_query(intent)
        if broad_query:
            queries.append(broad_query)

        return dedupe_queries(queries) or [intent.original_query]

    def build_date_url_query(self, intent: SearchIntent) -> str | None:
        """Build a query using a source's date URL template when available."""
        date_url = self.build_date_url(intent)
        if not date_url:
            return None
        terms = self.search_terms(intent)
        site_filter = date_url.removeprefix("https://").removeprefix("http://")
        return " ".join(part for part in (f"site:{site_filter}", terms) if part)

    def build_scoped_query(self, intent: SearchIntent) -> str | None:
        """Build a source-scoped query."""
        terms = self.search_terms(intent)
        date_part = self.date_query_part(intent)
        if intent.source:
            return " ".join(
                part
                for part in (
                    f"site:{intent.source.site}",
                    terms,
                    date_part,
                    intent.original_query,
                )
                if part
            )
        if date_part:
            return f"{intent.original_query} {date_part}"
        return intent.original_query

    def build_broad_query(self, intent: SearchIntent) -> str:
        """Build a broad fallback query."""
        terms = self.search_terms(intent)
        date_part = self.date_query_part(intent)
        return " ".join(part for part in (terms, date_part, intent.original_query) if part)

    def build_date_url(self, intent: SearchIntent) -> str | None:
        """Render source content date URL when a one-day constraint exists."""
        template = intent.content_type.date_url_template if intent.content_type else None
        exact_date = intent.temporal.exact_date
        if not template or not exact_date:
            return None
        return template.format(date=exact_date)

    def search_terms(self, intent: SearchIntent) -> str:
        """Return source/content search terms."""
        if intent.content_type and intent.content_type.search_terms:
            return " ".join(intent.content_type.search_terms)
        if intent.source:
            return intent.source.canonical_name
        return ""

    def date_query_part(self, intent: SearchIntent) -> str:
        """Return a date or date range query fragment."""
        exact_date = intent.temporal.exact_date
        if exact_date:
            return exact_date
        if intent.temporal.date_from and intent.temporal.date_to:
            return f"{intent.temporal.date_from}..{intent.temporal.date_to}"
        if intent.temporal.date_to and intent.temporal.freshness_required:
            return intent.temporal.date_to
        return ""


def dedupe_queries(queries: list[str]) -> list[str]:
    """Deduplicate non-empty queries while preserving order."""
    deduped = []
    for query in queries:
        normalized = " ".join(query.split())
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped
