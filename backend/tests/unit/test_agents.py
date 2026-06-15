"""Tests for individual agents."""

from datetime import datetime

import pytest

from src.agents.assistant_agent import AssistantAgent
from src.graph.state import create_initial_state
from src.search.direct_fetch import DirectFetchResult


class NoopDirectFetcher:
    async def fetch(self, plan):
        return DirectFetchResult.empty(url=plan.date_url)


class TestAssistantAgent:
    """Test cases for the unified assistant agent."""

    @pytest.mark.asyncio
    async def test_generates_response(self, mock_llm, mock_memory):
        """Assistant should generate a response for ordinary chat."""
        agent = AssistantAgent(llm=mock_llm, memory=mock_memory)
        state = create_initial_state("Hello!", "test-session")
        result = await agent.process(state)

        assert len(result["messages"]) == 2
        assert result["messages"][-1]["role"] == "assistant"
        assert result["completed_steps"] == ["assistant"]
        assert result["tool_results"] == []

    @pytest.mark.asyncio
    async def test_uses_memory(self, mock_llm):
        """Assistant should store user and assistant messages."""
        from src.memory.in_memory_store import InMemoryStore

        memory = InMemoryStore()
        agent = AssistantAgent(llm=mock_llm, memory=memory)
        state = create_initial_state("Hello!", "test-session")
        await agent.process(state)

        messages = await memory.get_messages("test-session")
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_retriever_uses_session_and_device_scope(self, mock_llm, mock_memory):
        """Assistant should search the user's uploaded-document namespace."""

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
        agent = AssistantAgent(llm=mock_llm, memory=mock_memory, retriever=retriever)
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
        assert result["tool_results"][0]["confidence"] == "none"

    @pytest.mark.asyncio
    async def test_web_search_tool_decision_executes_search(self, mock_llm, mock_memory):
        """Assistant should execute selected web search evidence tool."""

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
        agent = AssistantAgent(llm=mock_llm, memory=mock_memory, search_tool=search_tool)
        state = create_initial_state("오늘 AI 뉴스 검색해줘", "test-session")

        result = await agent.process(state)

        assert search_tool.calls
        assert "오늘 AI 뉴스 검색해줘" in search_tool.calls[0]
        assert result["messages"][-1]["role"] == "assistant"
        assert result["tool_results"][0]["tool"] == "web_search"

    @pytest.mark.asyncio
    async def test_huggingface_today_papers_request_has_current_date_context(
        self, mock_memory, monkeypatch
    ):
        """Today/current web requests should not rely on the model's stale internal date."""

        class RecordingLLM:
            config = type("Config", (), {"model": "mock-model"})()

            def __init__(self):
                self.messages = []

            async def generate_structured(self, messages, output_schema, **kwargs):
                return {
                    "tools": ["web_search"],
                    "response_mode": "answer",
                    "reasoning": "today papers",
                }

            async def generate_with_usage(self, messages, **kwargs):
                self.messages = messages
                return "검색 결과입니다.", {"input_tokens": 1, "output_tokens": 1}

        class MockSearchTool:
            def __init__(self):
                self.calls = []

            async def execute(self, query):
                self.calls.append(query)
                return "### [Daily Papers](https://huggingface.co/papers/date/2026-06-14)\n검색 결과"

        monkeypatch.setattr(
            "src.agents.assistant_agent.current_date_context",
            lambda: "Current date: 2026-06-15 (Asia/Seoul).",
        )
        monkeypatch.setattr(
            "src.search.temporal.current_datetime",
            lambda timezone="Asia/Seoul": datetime.fromisoformat("2026-06-15T09:00:00+09:00"),
        )
        monkeypatch.setattr(
            "src.agents.research_evidence.current_date_context",
            lambda: "Current date: 2026-06-15 (Asia/Seoul).",
        )

        llm = RecordingLLM()
        search_tool = MockSearchTool()
        agent = AssistantAgent(
            llm=llm,
            memory=mock_memory,
            search_tool=search_tool,
            direct_fetcher=NoopDirectFetcher(),
        )
        state = create_initial_state("hf에서 오늘자 논문 검색해줘", "test-session")

        result = await agent.process(state)

        system_prompt = "\n".join(
            message["content"] for message in llm.messages if message["role"] == "system"
        )
        assert "Current date: 2026-06-15 (Asia/Seoul)." in system_prompt
        assert search_tool.calls == [
            "site:huggingface.co/papers/date/2026-06-15 Hugging Face Daily Papers"
        ]
        assert result["tool_results"][0]["query"] == search_tool.calls[0]
        assert result["tool_results"][0]["search_plan"]["source_id"] == "huggingface"

    @pytest.mark.asyncio
    async def test_fallback_prefers_retriever_for_explicit_rag_query(self, mock_llm, mock_memory):
        """Fallback tool choice should not web-search explicit uploaded-document questions."""

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
        agent = AssistantAgent(
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

    @pytest.mark.asyncio
    async def test_assistant_uses_retriever_for_document_evidence(self, mock_llm, mock_memory):
        """Assistant should collect uploaded-document evidence without a router."""

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
                        "score": 0.9,
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
        agent = AssistantAgent(llm=mock_llm, memory=mock_memory, retriever=retriever)
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
        assert result["completed_steps"] == ["assistant"]
        assert result["tool_results"][0]["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_llm_under_selection_still_uses_retriever_for_rag_query(
        self, mock_llm, mock_memory
    ):
        """Explicit RAG questions should use retriever even when the LLM omits tools."""

        class MockRetrieverTool:
            async def execute(self, query, top_k=3, session_id=None, device_id=None):
                return [{"content": "리스트 A", "metadata": {"source": "doc.txt"}}]

        async def mock_generate_structured(messages, output_schema, **kwargs):
            return {"tools": [], "response_mode": "answer", "reasoning": "under-selected"}

        mock_llm.generate_structured = mock_generate_structured
        agent = AssistantAgent(llm=mock_llm, memory=mock_memory, retriever=MockRetrieverTool())
        state = create_initial_state(
            "지금 rag 문서에 있는 모든 리스트 알려줘",
            "test-session",
            "device-1",
        )
        state["has_documents"] = True

        result = await agent.process(state)

        assert [tool_result["tool"] for tool_result in result["tool_results"]] == ["retriever"]

    @pytest.mark.asyncio
    async def test_document_summary_request_uses_retriever_not_memory_summary(
        self, mock_llm, mock_memory
    ):
        """A bare summary request should summarize uploaded documents when they exist."""

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
                        "content": "IEEE 문서 요약 근거",
                        "metadata": {"source": "ieee.pdf"},
                        "score": 0.9,
                    }
                ]

        retriever = MockRetrieverTool()
        agent = AssistantAgent(llm=mock_llm, memory=mock_memory, retriever=retriever)
        state = create_initial_state("요약해줘", "test-session", "device-1")
        state["has_documents"] = True

        result = await agent.process(state)

        assert retriever.calls == [
            {
                "query": "요약해줘",
                "top_k": 3,
                "session_id": "test-session",
                "device_id": "device-1",
            }
        ]
        assert [tool_result["tool"] for tool_result in result["tool_results"]] == ["retriever"]

    @pytest.mark.asyncio
    async def test_missing_document_evidence_adds_abstention_warning(self, mock_memory):
        """Document questions with empty retrieval should receive explicit abstention guidance."""

        class RecordingLLM:
            config = type("Config", (), {"model": "mock-model"})()

            def __init__(self):
                self.messages = []

            async def generate_structured(self, messages, output_schema, **kwargs):
                return {
                    "tools": ["retriever"],
                    "response_mode": "answer",
                    "reasoning": "document query",
                }

            async def generate_with_usage(self, messages, **kwargs):
                self.messages = messages
                return "문서 근거가 부족합니다.", {"input_tokens": 1, "output_tokens": 1}

        class EmptyRetrieverTool:
            async def execute(self, query, top_k=3, session_id=None, device_id=None):
                return []

        llm = RecordingLLM()
        agent = AssistantAgent(llm=llm, memory=mock_memory, retriever=EmptyRetrieverTool())
        state = create_initial_state("업로드 문서에서 SLA를 찾아줘", "test-session", "device-1")
        state["has_documents"] = True

        result = await agent.process(state)

        evidence_prompt = "\n".join(
            message["content"] for message in llm.messages if message["role"] == "system"
        )
        assert "No matching uploaded-document evidence was found" in evidence_prompt
        assert result["tool_results"][0]["evidence_items"] == []
