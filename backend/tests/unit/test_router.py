"""Tests for the graph router."""

import pytest

from src.graph.router import LLMRouterNode, heuristic_route
from src.graph.state import create_initial_state


class FakeRouterLLM:
    def __init__(self, decision=None, error: Exception | None = None):
        self.decision = decision or {"agent": "chat", "reasoning": "test route"}
        self.error = error
        self.calls = 0

    async def generate_structured(self, messages, output_schema, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.decision


@pytest.mark.asyncio
async def test_llm_router_uses_structured_route_decision():
    llm = FakeRouterLLM({"agent": "research", "reasoning": "document query"})
    router = LLMRouterNode(llm)
    state = create_initial_state(
        "지금 rag 문서에 있는 모든 리스트 알려줘",
        available_nodes=["chat", "research"],
    )

    result = await router(state)

    assert llm.calls == 1
    assert result["next_agent"] == "research"
    assert result["metadata"]["route_source"] == "llm"


@pytest.mark.asyncio
async def test_llm_router_falls_back_to_heuristic_on_failure():
    router = LLMRouterNode(FakeRouterLLM(error=RuntimeError("boom")))
    state = create_initial_state(
        "오늘 뉴스 검색해서 알려줘",
        available_nodes=["chat", "research"],
    )

    result = await router(state)

    assert result["next_agent"] == "research"
    assert result["metadata"]["route_source"] == "heuristic_fallback"


@pytest.mark.asyncio
async def test_code_query_routes_to_chat():
    state = create_initial_state(
        "python 코드 실행해줘",
        available_nodes=["chat", "research"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "chat"


@pytest.mark.asyncio
async def test_code_query_falls_back_to_chat_when_code_agent_unavailable():
    state = create_initial_state(
        "python 코드 실행해줘",
        available_nodes=["chat"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "chat"


@pytest.mark.asyncio
async def test_current_info_query_routes_to_research():
    state = create_initial_state(
        "오늘 뉴스 검색해서 알려줘",
        available_nodes=["chat", "research"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "research"


@pytest.mark.asyncio
async def test_document_query_routes_to_research_when_documents_exist():
    state = create_initial_state(
        "업로드한 문서에서 찾아줘",
        available_nodes=["chat", "research"],
    )
    state["has_documents"] = True

    result = await heuristic_route(state)

    assert result["next_agent"] == "research"


@pytest.mark.asyncio
async def test_explicit_rag_query_routes_to_research():
    state = create_initial_state(
        "지금 rag 문서에 있는 모든 리스트 알려줘",
        available_nodes=["chat", "research"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "research"


@pytest.mark.asyncio
async def test_report_query_routes_to_research():
    state = create_initial_state(
        "최신 자료와 문서를 종합해서 보고서 작성해줘",
        available_nodes=["chat", "research"],
    )
    state["has_documents"] = True

    result = await heuristic_route(state)

    assert result["next_agent"] == "research"
