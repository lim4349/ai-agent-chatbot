"""Tests for Supervisor Agent."""

import pytest

from src.agents.supervisor import SupervisorAgent
from src.graph.state import create_initial_state


class TestSupervisorAgent:
    """Test cases for Supervisor Agent."""

    @pytest.mark.asyncio
    async def test_routes_to_chat(self, mock_llm):
        """Test that greetings are routed to chat."""
        async def mock_structured(messages, output_schema, **kwargs):
            return {"selected_agent": "chat", "reasoning": "General greeting"}
        mock_llm.generate_structured = mock_structured

        supervisor = SupervisorAgent(llm=mock_llm, available_agents={"chat", "code", "web_search"})
        state = create_initial_state("안녕하세요!", "test-session")
        result = await supervisor.process(state)

        assert result["next_agent"] == "chat"
        assert "route_reasoning" in result["metadata"]

    @pytest.mark.asyncio
    async def test_routes_to_code(self, mock_llm):
        """Test that code requests are routed to code agent."""
        async def mock_structured(messages, output_schema, **kwargs):
            return {"selected_agent": "code", "reasoning": "Code generation request"}
        mock_llm.generate_structured = mock_structured

        supervisor = SupervisorAgent(llm=mock_llm, available_agents={"chat", "code", "web_search"})
        state = create_initial_state("파이썬으로 피보나치 함수 작성해줘", "test-session")
        result = await supervisor.process(state)

        assert result["next_agent"] == "code"

    @pytest.mark.asyncio
    async def test_routes_to_web_search(self, mock_llm):
        """Test that current info requests are routed to web search."""
        async def mock_structured(messages, output_schema, **kwargs):
            return {"selected_agent": "web_search", "reasoning": "Current information needed"}
        mock_llm.generate_structured = mock_structured

        supervisor = SupervisorAgent(llm=mock_llm, available_agents={"chat", "code", "web_search"})
        state = create_initial_state("오늘 서울 날씨 어때?", "test-session")
        result = await supervisor.process(state)

        assert result["next_agent"] == "web_search"
