"""Tests for the heuristic graph router."""

import pytest

from src.graph.router import heuristic_route
from src.graph.state import create_initial_state


@pytest.mark.asyncio
async def test_code_query_routes_to_code_when_code_agent_available():
    state = create_initial_state(
        "python 코드 실행해줘",
        available_nodes=["chat", "code", "rag", "report"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "code"
    assert result["remaining_tasks"] == ["code"]


@pytest.mark.asyncio
async def test_code_query_falls_back_to_chat_when_code_agent_unavailable():
    state = create_initial_state(
        "python 코드 실행해줘",
        available_nodes=["chat", "report"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "chat"
    assert result["remaining_tasks"] == ["chat"]


@pytest.mark.asyncio
async def test_current_info_query_uses_chat_with_web_search_hint():
    state = create_initial_state(
        "오늘 뉴스 검색해서 알려줘",
        available_nodes=["chat", "web_search_collect", "report"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "web_search_collect"
    assert result["remaining_tasks"] == ["web_search_collect", "chat"]


@pytest.mark.asyncio
async def test_document_query_routes_to_retriever_then_rag_when_documents_exist():
    state = create_initial_state(
        "업로드한 문서에서 찾아줘",
        available_nodes=["chat", "rag", "retriever_collect", "report"],
    )
    state["has_documents"] = True

    result = await heuristic_route(state)

    assert result["next_agent"] == "retriever_collect"
    assert result["remaining_tasks"] == ["retriever_collect", "rag"]


@pytest.mark.asyncio
async def test_report_query_collects_available_context_then_report():
    state = create_initial_state(
        "최신 자료와 문서를 종합해서 보고서 작성해줘",
        available_nodes=[
            "chat",
            "rag",
            "report",
            "web_search_collect",
            "retriever_collect",
        ],
    )
    state["has_documents"] = True

    result = await heuristic_route(state)

    assert result["next_agent"] == "web_search_collect"
    assert result["remaining_tasks"] == [
        "web_search_collect",
        "retriever_collect",
        "report",
    ]
