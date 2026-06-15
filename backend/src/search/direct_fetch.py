"""Direct source fetching for planned search URLs."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx

from src.core.logging import get_logger
from src.search.models import SearchQueryPlan

logger = get_logger(__name__)

DEFAULT_FETCH_LIMIT = 5
MAX_FETCH_LIMIT = 10
SNIPPET_LIMIT = 420


@dataclass(frozen=True)
class DirectFetchItem:
    """One structured item extracted from a source page."""

    title: str
    url: str
    snippet: str = ""
    date: str | None = None
    score: int | None = None
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        """Return a JSON-safe representation."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "date": self.date,
            "score": self.score,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DirectFetchResult:
    """Structured result from a direct source fetch."""

    url: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    extractor: str | None = None
    items: list[DirectFetchItem] = field(default_factory=list)
    text: str = ""
    error: str | None = None

    @classmethod
    def empty(cls, *, url: str | None = None, error: str | None = None) -> DirectFetchResult:
        """Return an empty direct-fetch result."""
        return cls(url=url, error=error)

    def as_dict(self) -> dict:
        """Return a JSON-safe representation."""
        return {
            "url": self.url,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "extractor": self.extractor,
            "items": [item.as_dict() for item in self.items],
            "error": self.error,
        }


class DirectSourceFetcher:
    """Fetch exact source URLs emitted by the search planner."""

    def __init__(self, *, timeout: float = 10.0, max_items: int = MAX_FETCH_LIMIT) -> None:
        self.timeout = timeout
        self.max_items = max(1, min(max_items, MAX_FETCH_LIMIT))

    async def fetch(self, plan: SearchQueryPlan) -> DirectFetchResult:
        """Fetch and extract structured evidence from a planned source URL."""
        if not plan.date_url or not plan.direct_fetch_extractor:
            return DirectFetchResult.empty(url=plan.date_url)

        extractor = DIRECT_FETCH_EXTRACTORS.get(plan.direct_fetch_extractor)
        if extractor is None:
            return DirectFetchResult.empty(
                url=plan.date_url,
                error=f"unsupported direct fetch extractor: {plan.direct_fetch_extractor}",
            )

        try:
            html_text, status_code, content_type = await self.fetch_html(plan.date_url)
        except Exception as exc:
            logger.warning("direct_source_fetch_failed", url=plan.date_url, error=str(exc))
            return DirectFetchResult.empty(url=plan.date_url, error=str(exc))

        if status_code >= 400:
            return DirectFetchResult.empty(
                url=plan.date_url,
                error=f"source returned HTTP {status_code}",
            )

        items = extractor(html_text, plan.date_url)
        if not items:
            return DirectFetchResult(
                url=plan.date_url,
                status_code=status_code,
                content_type=content_type,
                extractor=plan.direct_fetch_extractor,
                error="no structured items extracted",
            )

        limit = requested_item_limit(plan.original_query, self.max_items)
        limited_items = items[:limit]
        text = format_direct_source_text(plan, plan.date_url, limited_items)
        return DirectFetchResult(
            url=plan.date_url,
            status_code=status_code,
            content_type=content_type,
            extractor=plan.direct_fetch_extractor,
            items=limited_items,
            text=text,
        )

    async def fetch_html(self, url: str) -> tuple[str, int, str | None]:
        """Fetch HTML from an exact source URL."""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "ai-agent-chatbot/1.0 (+https://github.com)",
        }
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers=headers,
            timeout=self.timeout,
        ) as client:
            response = await client.get(url)
        return response.text, response.status_code, response.headers.get("content-type")


def parse_huggingface_daily_papers(html_text: str, page_url: str) -> list[DirectFetchItem]:
    """Extract paper cards from Hugging Face's serialized daily-papers page data."""
    text = html.unescape(html_text)
    decoder = json.JSONDecoder()
    items: list[DirectFetchItem] = []
    seen_ids: set[str] = set()

    for match in re.finditer(r'\{"paper":\{"id":"', text):
        try:
            raw_item, _ = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue

        if not isinstance(raw_item, dict) or not isinstance(raw_item.get("paper"), dict):
            continue

        paper = raw_item["paper"]
        paper_id = normalize_space(paper.get("id"))
        title = normalize_space(paper.get("title"))
        if not paper_id or not title or paper_id in seen_ids:
            continue

        seen_ids.add(paper_id)
        submitted_at = normalize_space(
            paper.get("submittedOnDailyAt") or raw_item.get("submittedOnDailyAt")
        )
        authors = [
            normalize_space(author.get("name"))
            for author in paper.get("authors", [])
            if isinstance(author, dict) and normalize_space(author.get("name"))
        ]
        items.append(
            DirectFetchItem(
                title=title,
                url=urljoin(page_url, f"/papers/{paper_id}"),
                snippet=normalize_space(paper.get("summary"), limit=SNIPPET_LIMIT),
                date=submitted_at[:10] if submitted_at else None,
                score=safe_int(paper.get("upvotes")),
                metadata={
                    "paper_id": paper_id,
                    "authors": authors[:5],
                    "github_repo": paper.get("githubRepo"),
                },
            )
        )

    return sorted(items, key=lambda item: item.score if item.score is not None else -1, reverse=True)


def requested_item_limit(query: str, max_items: int = MAX_FETCH_LIMIT) -> int:
    """Infer a bounded result count from a user query."""
    patterns = (
        r"(?:top|상위)\s*(\d{1,2})",
        r"(\d{1,2})\s*(?:개|편)",
    )
    lowered = query.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return max(1, min(int(match.group(1)), max_items))
    return min(DEFAULT_FETCH_LIMIT, max_items)


def format_direct_source_text(
    plan: SearchQueryPlan,
    source_url: str,
    items: list[DirectFetchItem],
) -> str:
    """Format direct-source evidence in the same markdown-link shape as search results."""
    source_name = plan.source_name or plan.site or "Direct source"
    content_type = plan.content_type or "results"
    exact_date = plan.temporal.exact_date
    source_label = " ".join(part for part in (source_name, content_type, exact_date) if part)
    lines = [
        f"## Direct source: {source_label}",
        f"Source: [{markdown_link_text(source_label)}]({source_url})",
    ]

    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                "",
                f"### {index}. [{markdown_link_text(item.title)}]({item.url})",
                f"Votes: {item.score}" if item.score is not None else "Votes: unknown",
                f"Daily date: {item.date}" if item.date else "Daily date: unknown",
            ]
        )
        authors = item.metadata.get("authors") if isinstance(item.metadata, dict) else None
        if authors:
            lines.append(f"Authors: {', '.join(authors)}")
        if item.snippet:
            lines.append(f"Summary: {item.snippet}")

    return "\n".join(lines)


def normalize_space(value: object, *, limit: int | None = None) -> str:
    """Normalize whitespace and optionally bound text length."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if limit is not None and len(text) > limit:
        return text[: max(limit - 3, 0)].rstrip() + "..."
    return text


def safe_int(value: object) -> int | None:
    """Return an int when possible."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def markdown_link_text(value: str) -> str:
    """Escape markdown link title delimiters."""
    return value.replace("[", r"\[").replace("]", r"\]")


DIRECT_FETCH_EXTRACTORS = {
    "huggingface_daily_papers": parse_huggingface_daily_papers,
}
