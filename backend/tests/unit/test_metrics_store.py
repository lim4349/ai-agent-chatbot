"""Tests for assistant observability metrics."""

import pytest
from fastapi import HTTPException

from src.api.routes import get_metrics_summary
from src.core.config import DEFAULT_LLM_MODEL
from src.observability.metrics_store import MetricsStore


@pytest.mark.asyncio
async def test_metrics_store_summary_aggregates_quality_stats():
    store = MetricsStore()

    await store.record_request(
        session_id="session-1",
        agent_name="assistant",
        duration_ms=1200,
        model_name=DEFAULT_LLM_MODEL,
        input_tokens=10,
        output_tokens=20,
        status="success",
        metadata={
            "evidence_count": 2,
            "evidence_confidence": "high",
            "evidence_tools": ["web_search", "retriever"],
        },
    )
    await store.record_request(
        session_id="session-2",
        agent_name="assistant",
        duration_ms=300,
        model_name=DEFAULT_LLM_MODEL,
        input_tokens=5,
        output_tokens=7,
        status="error",
        metadata={
            "evidence_count": 0,
            "evidence_confidence": "none",
            "evidence_tools": [],
        },
    )
    await store.record_request(
        session_id="session-3",
        agent_name="assistant",
        duration_ms=900,
        model_name=DEFAULT_LLM_MODEL,
        input_tokens=3,
        output_tokens=4,
        status="blocked",
        metadata={
            "evidence_count": 0,
            "evidence_confidence": "error",
            "evidence_tools": ["retriever"],
        },
    )

    summary = await store.get_summary("24h")

    assert summary["total_requests"] == 3
    assert summary["success_count"] == 1
    assert summary["error_count"] == 1
    assert summary["timeout_count"] == 1
    assert summary["avg_duration_ms"] == 800
    assert summary["total_input_tokens"] == 18
    assert summary["total_output_tokens"] == 31
    assert "agent_stats" not in summary
    assert summary["quality_stats"] == {
        "evidence_turns": 1,
        "no_evidence_turns": 2,
        "evidence_rate": pytest.approx(1 / 3),
        "confidence_counts": {"high": 1, "none": 1, "error": 1},
        "tool_counts": {"web_search": 1, "retriever": 2},
    }


@pytest.mark.asyncio
async def test_metrics_summary_route_rejects_invalid_period():
    with pytest.raises(HTTPException) as exc_info:
        await get_metrics_summary(period="90d", metrics_store=MetricsStore())

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_metrics_summary_route_returns_dashboard_contract():
    store = MetricsStore()
    await store.record_request(
        session_id="session-1",
        agent_name="assistant",
        duration_ms=100,
        model_name=DEFAULT_LLM_MODEL,
        input_tokens=1,
        output_tokens=2,
        status="success",
        metadata={"evidence_count": 0, "evidence_confidence": "none"},
    )

    response = await get_metrics_summary(period="24h", metrics_store=store)
    data = response.model_dump()

    assert data["total_requests"] == 1
    assert data["successful_requests"] == 1
    assert data["total_tokens"] == 3
    assert "quality_stats" in data
    assert "agent_stats" not in data
