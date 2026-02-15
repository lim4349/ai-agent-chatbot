"""Integration tests for the LangGraph.

Note: These tests require proper mock setup or API keys.
"""

import pytest

from src.core.container import Container


class TestGraphIntegration:
    """Integration tests for the complete graph."""

    @pytest.mark.asyncio
    async def test_graph_processes_message(self, test_container: Container):
        """Test that the graph processes a message end-to-end."""
        from src.graph.state import create_initial_state

        # Verify mock is set
        if test_container._llm_override is None:
            pytest.skip("Mock LLM not properly configured")

        graph = test_container.graph
        state = create_initial_state("Hello!", "test-session")

        result = await graph.ainvoke(state)

        # Check we got a response
        assert "messages" in result
        assert len(result["messages"]) >= 2
        assert result["messages"][-1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_graph_routes_to_chat(self, test_container: Container):
        """Test that the graph routes general chat to chat agent."""
        from src.graph.state import create_initial_state

        # Verify mock is set
        mock_llm = test_container._llm_override
        if mock_llm is None:
            pytest.skip("Mock LLM not properly configured")

        async def mock_structured(messages, output_schema, **kwargs):
            return {"next_agent": "chat", "reasoning": "General greeting"}

        mock_llm.generate_structured = mock_structured

        graph = test_container.graph
        state = create_initial_state("안녕하세요!", "test-session")

        result = await graph.ainvoke(state)

        assert result.get("next_agent") == "chat"
