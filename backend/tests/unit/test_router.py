"""Tests for the heuristic graph router."""

import pytest

from src.graph.router import heuristic_route
from src.graph.state import create_initial_state


@pytest.mark.asyncio
async def test_code_query_routes_to_code_when_code_agent_available():
    state = create_initial_state(
        "python 코드 실행해줘",
        available_agents=["supervisor", "chat", "code", "report"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "code"
    assert result["tools_hint"] == []


@pytest.mark.asyncio
async def test_code_query_falls_back_to_chat_when_code_agent_unavailable():
    state = create_initial_state(
        "python 코드 실행해줘",
        available_agents=["supervisor", "chat", "report"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "chat"
    assert result["tools_hint"] == []


@pytest.mark.asyncio
async def test_current_info_query_uses_chat_with_web_search_hint():
    state = create_initial_state(
        "오늘 뉴스 검색해서 알려줘",
        available_agents=["supervisor", "chat", "web_search", "report"],
    )

    result = await heuristic_route(state)

    assert result["next_agent"] == "chat"
    assert result["tools_hint"] == ["web_search"]
