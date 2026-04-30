"""Tests for individual agents."""

import pytest

from src.agents.chat_agent import ChatAgent
from src.agents.research_agent import ResearchAgent
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

class TestResearchAgent:
    """Test cases for Research Agent."""

    @pytest.mark.asyncio
    async def test_retriever_uses_session_and_device_scope(self, mock_llm, mock_memory):
        """Document retrieval should search the user's uploaded-document namespace."""

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

        async def mock_generate_structured(messages, output_schema, **kwargs):
            return {
                "tools": ["retriever"],
                "response_mode": "answer",
                "reasoning": "document query",
            }

        mock_llm.generate_structured = mock_generate_structured
        retriever = MockRetrieverTool()
        agent = ResearchAgent(llm=mock_llm, memory=mock_memory, retriever=retriever)
        state = create_initial_state("문서에서 찾아줘", "test-session", "device-1")
        state["has_documents"] = True

        result = await agent.process(state)

        assert retriever.calls == [
            {
                "query": "문서에서 찾아줘",
                "top_k": 3,
                "session_id": "test-session",
                "device_id": "device-1",
            }
        ]
        assert result["messages"][-1]["role"] == "assistant"
        assert result["tool_results"][0]["tool"] == "retriever"

    @pytest.mark.asyncio
    async def test_web_search_tool_decision_executes_search(self, mock_llm, mock_memory):
        """Research agent should execute selected web search tool."""

        class MockSearchTool:
            def __init__(self):
                self.calls = []

            async def execute(self, query):
                self.calls.append(query)
                return "### [Source](https://example.com)\n검색 결과"

        async def mock_generate_structured(messages, output_schema, **kwargs):
            return {
                "tools": ["web_search"],
                "response_mode": "answer",
                "reasoning": "current info",
            }

        mock_llm.generate_structured = mock_generate_structured
        search_tool = MockSearchTool()
        agent = ResearchAgent(llm=mock_llm, memory=mock_memory, search_tool=search_tool)
        state = create_initial_state("오늘 AI 뉴스 검색해줘", "test-session")

        result = await agent.process(state)

        assert search_tool.calls == ["오늘 AI 뉴스 검색해줘"]
        assert result["messages"][-1]["role"] == "assistant"
        assert result["tool_results"][0]["tool"] == "web_search"

    @pytest.mark.asyncio
    async def test_fallback_prefers_retriever_for_explicit_rag_query(self, mock_llm, mock_memory):
        """Fallback tool routing should not web-search explicit uploaded-document questions."""

        class MockSearchTool:
            def __init__(self):
                self.calls = []

            async def execute(self, query):
                self.calls.append(query)
                return "검색 결과"

        class MockRetrieverTool:
            async def execute(self, query, top_k=3, session_id=None, device_id=None):
                return [{"content": "리스트 A", "metadata": {"source": "doc.txt"}}]

        async def mock_generate_structured(messages, output_schema, **kwargs):
            raise RuntimeError("structured output unavailable")

        mock_llm.generate_structured = mock_generate_structured
        search_tool = MockSearchTool()
        agent = ResearchAgent(
            llm=mock_llm,
            memory=mock_memory,
            search_tool=search_tool,
            retriever=MockRetrieverTool(),
        )
        state = create_initial_state(
            "지금 rag 문서에 있는 모든 리스트 알려줘",
            "test-session",
            "device-1",
        )
        state["has_documents"] = True

        result = await agent.process(state)

        assert search_tool.calls == []
        assert [tool_result["tool"] for tool_result in result["tool_results"]] == ["retriever"]
