"""Tests for individual agents."""

import pytest

from src.agents.chat_agent import ChatAgent
from src.agents.code_agent import CodeAgent
from src.agents.report_agent import ReportAgent
from src.graph.state import create_initial_state


class TestChatAgent:
    """Test cases for Chat Agent."""

    @pytest.mark.asyncio
    async def test_generates_response(self, mock_llm, mock_memory):
        """Test that chat agent generates a response."""
        agent = ChatAgent(llm=mock_llm, memory=mock_memory)
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

    @pytest.mark.asyncio
    async def test_retriever_prefetch_uses_session_and_device_scope(self, mock_llm, mock_memory):
        """Document prefetch should search the user's uploaded-document namespace."""

        class MockRetrieverTool:
            def __init__(self):
                self.calls = []

            async def execute(self, query, top_k=3, session_id=None, device_id=None):
                self.calls.append(
                    {
                        "query": query,
                        "top_k": top_k,
                        "session_id": session_id,
                        "device_id": device_id,
                    }
                )
                return [
                    {
                        "content": "문서 내용",
                        "metadata": {"source": "doc.txt"},
                    }
                ]

        retriever = MockRetrieverTool()
        agent = ChatAgent(
            llm=mock_llm,
            memory=mock_memory,
            long_term_memory=None,
            user_profiler=None,
            topic_memory=None,
            summarizer=None,
            retriever=retriever,
        )
        state = create_initial_state("문서에서 찾아줘", "test-session", "device-1")
        state["has_documents"] = True
        state["tools_hint"] = ["retriever"]

        await agent.process(state)

        assert retriever.calls == [
            {
                "query": "문서에서 찾아줘",
                "top_k": 3,
                "session_id": "test-session",
                "device_id": "device-1",
            }
        ]


class TestCodeAgent:
    """Test cases for Code Agent."""

    @pytest.mark.asyncio
    async def test_generates_code_response(self, mock_llm, mock_memory):
        """Test that code agent generates a response."""

        async def mock_generate_with_usage(messages, **kwargs):
            return "```python\nprint('Hello')\n```", {"input_tokens": 10, "output_tokens": 20}

        mock_llm.generate_with_usage = mock_generate_with_usage

        agent = CodeAgent(llm=mock_llm, memory=mock_memory)
        state = create_initial_state("Write a hello world program", "test-session")
        result = await agent.process(state)

        assert len(result["messages"]) == 2
        assert "```python" in result["messages"][-1]["content"]


class TestReportAgent:
    """Test cases for Report Agent."""

    @pytest.mark.asyncio
    async def test_direct_report_uses_web_search_context(self, mock_llm, mock_memory):
        """Report route should work when called outside the task-queue graph."""

        class MockSearchTool:
            def __init__(self):
                self.calls = []

            async def execute(self, query):
                self.calls.append(query)
                return "### [Source](https://example.com)\n검색 결과"

        search_tool = MockSearchTool()
        agent = ReportAgent(llm=mock_llm, memory=mock_memory, search_tool=search_tool)
        state = create_initial_state("AI 시장 보고서 작성해줘", "test-session")
        state["tools_hint"] = ["web_search"]

        result = await agent.process(state)

        assert search_tool.calls == ["AI 시장 보고서 작성해줘"]
        assert result["messages"][-1]["role"] == "assistant"
        assert result["tool_results"][0]["tool"] == "web_search"
