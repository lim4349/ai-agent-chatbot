"""Tests for individual agents."""

import pytest

from src.agents.chat_agent import ChatAgent
from src.agents.code_agent import CodeAgent
from src.graph.state import create_initial_state


class TestChatAgent:
    """Test cases for Chat Agent."""

    @pytest.mark.asyncio
    async def test_generates_response(self, mock_llm):
        """Test that chat agent generates a response."""
        agent = ChatAgent(llm=mock_llm)
        state = create_initial_state("Hello!", "test-session")
        result = await agent.process(state)

        assert len(result["messages"]) == 2
        assert result["messages"][-1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_uses_memory(self, mock_llm):
        """Test that chat agent uses memory when available."""
        from src.memory.in_memory_store import InMemoryStore

        memory = InMemoryStore()
        agent = ChatAgent(llm=mock_llm, memory=memory)
        state = create_initial_state("Hello!", "test-session")
        await agent.process(state)

        # Check memory was updated
        messages = await memory.get_messages("test-session")
        assert len(messages) == 2  # user + assistant


class TestCodeAgent:
    """Test cases for Code Agent."""

    @pytest.mark.asyncio
    async def test_generates_code_response(self, mock_llm):
        """Test that code agent generates a response."""

        async def mock_generate(messages, **kwargs):
            return "```python\nprint('Hello')\n```"

        mock_llm.generate = mock_generate

        agent = CodeAgent(llm=mock_llm)
        state = create_initial_state("Write a hello world program", "test-session")
        result = await agent.process(state)

        assert len(result["messages"]) == 2
        assert "```python" in result["messages"][-1]["content"]
