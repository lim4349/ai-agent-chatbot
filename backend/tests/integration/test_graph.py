"""Integration tests for the LangGraph.

Note: These tests require proper mock setup or API keys.
"""

import pytest


@pytest.mark.skip(reason="Integration tests require full mock setup - use unit tests instead")
class TestGraphIntegration:
    """Integration tests for the complete graph."""

    @pytest.mark.asyncio
    async def test_graph_processes_message(self):
        """Test that the graph processes a message end-to-end."""
        from src.core.di_container import container
        from src.graph.state import create_initial_state

        # Check if LLM is properly configured
        try:
            llm = container.llm()
            if llm is None:
                pytest.skip("LLM not configured")
        except Exception:
            pytest.skip("LLM not available")

        graph = container.graph()
        state = create_initial_state("Hello!", "test-session")

        result = await graph.ainvoke(state)

        # Check we got a response
        assert "messages" in result
        assert len(result["messages"]) >= 2
        assert result["messages"][-1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_graph_routes_to_chat(self):
        """Test that the graph routes general chat to chat agent."""
        from src.core.di_container import container
        from src.graph.state import create_initial_state

        # Check if LLM is properly configured
        try:
            llm = container.llm()
            if llm is None:
                pytest.skip("LLM not configured")
        except Exception:
            pytest.skip("LLM not available")

        graph = container.graph()
        state = create_initial_state("안녕하세요!", "test-session")

        result = await graph.ainvoke(state)

        assert result.get("next_agent") == "chat"
