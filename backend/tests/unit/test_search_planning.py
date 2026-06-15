"""Tests for generalized web search planning."""

import html
import json
from datetime import date

import pytest

from src.search.direct_fetch import DirectSourceFetcher, parse_huggingface_daily_papers
from src.search.evidence_dates import EvidenceDateValidator
from src.search.query_planner import SearchQueryPlanner
from src.search.source_profiles import ContentIntentResolver, SourceResolver
from src.search.temporal import TemporalResolver


def test_temporal_resolver_today_uses_asia_seoul_date():
    resolver = TemporalResolver(today_provider=lambda: date(2026, 6, 15))

    temporal = resolver.resolve("오늘자 논문 검색해줘")

    assert temporal.scope == "today"
    assert temporal.date_from == "2026-06-15"
    assert temporal.date_to == "2026-06-15"
    assert temporal.timezone == "Asia/Seoul"
    assert temporal.freshness_required is True


def test_source_resolver_matches_hf_with_korean_particle():
    source = SourceResolver().resolve("hf에서 오늘자 논문 검색해줘")

    assert source is not None
    assert source.id == "huggingface"


def test_content_resolver_matches_source_specific_papers():
    source = SourceResolver().resolve("허깅페이스 논문 찾아줘")
    content_type = ContentIntentResolver().resolve("허깅페이스 논문 찾아줘", source)

    assert content_type is not None
    assert content_type.id == "papers"
    assert content_type.date_url_template == "https://huggingface.co/papers/date/{date}"
    assert content_type.direct_fetch_extractor == "huggingface_daily_papers"


def test_query_planner_uses_date_template_when_available():
    planner = SearchQueryPlanner(today_provider=lambda: date(2026, 6, 15))

    plan = planner.plan("hf에서 오늘자 논문 검색해줘")

    assert plan.source_id == "huggingface"
    assert plan.source_name == "Hugging Face"
    assert plan.content_type == "papers"
    assert plan.temporal.exact_date == "2026-06-15"
    assert plan.date_url == "https://huggingface.co/papers/date/2026-06-15"
    assert plan.direct_fetch_extractor == "huggingface_daily_papers"
    assert plan.queries[0] == (
        "site:huggingface.co/papers/date/2026-06-15 Hugging Face Daily Papers"
    )
    assert plan.queries[1] == (
        "site:huggingface.co Hugging Face Daily Papers 2026-06-15 "
        "hf에서 오늘자 논문 검색해줘"
    )


def test_query_planner_falls_back_without_source_profile():
    planner = SearchQueryPlanner(today_provider=lambda: date(2026, 6, 15))

    plan = planner.plan("오늘 AI 뉴스 검색해줘")

    assert plan.source_id is None
    assert plan.content_type == "news"
    assert plan.temporal.exact_date == "2026-06-15"
    assert plan.queries == [
        "오늘 AI 뉴스 검색해줘 2026-06-15",
        "news 2026-06-15 오늘 AI 뉴스 검색해줘",
    ]


def test_evidence_date_validator_marks_stale_daily_page():
    planner = SearchQueryPlanner(today_provider=lambda: date(2026, 6, 15))
    plan = planner.plan("hf에서 오늘자 논문 검색해줘")

    validation = EvidenceDateValidator().validate_text(
        "### [Daily Papers](https://huggingface.co/papers/date/2026-06-12)\nOld result",
        plan,
    )

    assert validation.status == "stale"
    assert validation.expected_date == "2026-06-15"
    assert validation.latest_observed_date == "2026-06-12"
    assert validation.warning is not None


def test_huggingface_daily_papers_parser_extracts_upvote_sorted_items():
    html_text = build_huggingface_daily_html(
        [
            {
                "paper": {
                    "id": "2606.00001",
                    "title": "Lower Vote Paper",
                    "summary": "Less popular.",
                    "submittedOnDailyAt": "2026-06-15T00:00:00.000Z",
                    "upvotes": 3,
                    "authors": [{"name": "Alice"}],
                }
            },
            {
                "paper": {
                    "id": "2606.00002",
                    "title": "Higher Vote Paper",
                    "summary": "More popular.",
                    "submittedOnDailyAt": "2026-06-15T00:00:00.000Z",
                    "upvotes": 11,
                    "authors": [{"name": "Bob"}],
                }
            },
        ]
    )

    items = parse_huggingface_daily_papers(
        html_text,
        "https://huggingface.co/papers/date/2026-06-15",
    )

    assert [item.title for item in items] == ["Higher Vote Paper", "Lower Vote Paper"]
    assert items[0].score == 11
    assert items[0].date == "2026-06-15"
    assert items[0].url == "https://huggingface.co/papers/2606.00002"


@pytest.mark.asyncio
async def test_direct_fetcher_formats_huggingface_daily_papers_without_search_api():
    class FakeDirectSourceFetcher(DirectSourceFetcher):
        async def fetch_html(self, url: str) -> tuple[str, int, str | None]:
            return (
                build_huggingface_daily_html(
                    [
                        {
                            "paper": {
                                "id": "2606.00001",
                                "title": "Top Paper",
                                "summary": "The most relevant daily paper.",
                                "submittedOnDailyAt": "2026-06-15T00:00:00.000Z",
                                "upvotes": 42,
                                "authors": [{"name": "Alice"}],
                            }
                        }
                    ]
                ),
                200,
                "text/html; charset=utf-8",
            )

    planner = SearchQueryPlanner(today_provider=lambda: date(2026, 6, 15))
    plan = planner.plan("Hugging Face papers today votes top 5")

    result = await FakeDirectSourceFetcher().fetch(plan)

    assert result.error is None
    assert result.items[0].title == "Top Paper"
    assert result.items[0].score == 42
    assert "## Direct source: Hugging Face papers 2026-06-15" in result.text
    assert "### 1. [Top Paper](https://huggingface.co/papers/2606.00001)" in result.text
    assert "Votes: 42" in result.text
    assert "Daily date: 2026-06-15" in result.text


def build_huggingface_daily_html(records: list[dict]) -> str:
    """Build escaped page data shaped like Hugging Face's daily papers HTML."""
    payload = ",".join(json.dumps(record, separators=(",", ":")) for record in records)
    return html.escape(payload)
