"""Integration tests for the minimal LangGraph agent architecture."""

import pytest

from src.graph.builder import build_graph
from src.graph.state import create_initial_state


class CountingLLMConfig:
    model = "mock-model"


class CountingLLM:
    def __init__(self):
        self.config = CountingLLMConfig()
        self.calls = 0

    async def generate_with_usage(self, messages, **kwargs):
        self.calls += 1
        return "mock response", {"input_tokens": 1, "output_tokens": 1}

    async def generate_structured(self, messages, output_schema, **kwargs):
        self.calls += 1
        schema_name = getattr(output_schema, "__name__", "")
        if schema_name == "ResearchToolDecision":
            user_prompt = messages[-1]["content"]
            tools = []
            if "뉴스" in user_prompt or "검색" in user_prompt or "오늘" in user_prompt:
                tools.append("web_search")
            if "문서" in user_prompt or "업로드" in user_prompt or "rag" in user_prompt.lower():
                tools.append("retriever")
            if "보고서" in user_prompt or "종합" in user_prompt:
                tools = ["web_search", "retriever"]
            return {
                "tools": tools,
                "response_mode": "report" if "보고서" in user_prompt else "answer",
                "reasoning": "mock tool decision",
            }
        return {}


class MockMemory:
    async def get_messages(self, session_id):
        return []

    async def add_message(self, session_id, message):
        return None


class MockSearchTool:
    name = "web_search"

    async def execute(self, query):
        return "검색 결과"


class MockRetrieverTool:
    name = "retriever"

    async def execute(self, query, top_k=3, session_id=None, device_id=None):
        return [{"content": "문서 내용", "metadata": {"source": "doc.txt"}, "score": 0.9}]


class MockRetriever:
    async def retrieve(self, query, top_k=3, session_id=None, device_id=None):
        return [{"content": "문서 내용", "metadata": {"source": "doc.txt"}, "score": 0.9}]


class MockToolRegistry:
    def __init__(self):
        self.tools = {
            "web_search": MockSearchTool(),
            "retriever": MockRetrieverTool(),
        }

    def get(self, name):
        return self.tools.get(name)

    def list_tools(self):
        return list(self.tools)


class MockContainer:
    def __init__(self, llm):
        self._llm = llm
        self._memory = MockMemory()
        self._retriever = MockRetriever()
        self._tool_registry = MockToolRegistry()

    def llm(self):
        return self._llm

    def memory(self):
        return self._memory

    def retriever(self):
        return self._retriever

    def tool_registry(self):
        return self._tool_registry

    def long_term_memory(self):
        return None

    def user_profiler(self):
        return None

    def topic_memory(self):
        return None

    def summarizer(self):
        return None


def _config(name: str):
    return {"configurable": {"thread_id": name}}


@pytest.mark.asyncio
async def test_graph_assistant_uses_web_tool_for_web_query():
    llm = CountingLLM()
    graph = build_graph(MockContainer(llm))
    state = create_initial_state(
        "오늘 뉴스 검색해서 알려줘",
        "test-session",
        "device-1",
        ["assistant"],
    )

    result = await graph.ainvoke(state, config=_config("web-search"))

    assert result["completed_steps"] == ["assistant"]
    assert result["tool_results"][0]["tool"] == "web_search"
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_graph_assistant_uses_retriever_for_document_query():
    llm = CountingLLM()
    graph = build_graph(MockContainer(llm))
    state = create_initial_state(
        "업로드한 문서에서 찾아줘",
        "test-session",
        "device-1",
        ["assistant"],
    )
    state["has_documents"] = True

    result = await graph.ainvoke(state, config=_config("rag"))

    assert result["completed_steps"] == ["assistant"]
    assert result["tool_results"][0]["tool"] == "retriever"
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_graph_assistant_uses_both_tools_for_report_query():
    llm = CountingLLM()
    graph = build_graph(MockContainer(llm))
    state = create_initial_state(
        "최신 자료와 문서를 종합해서 보고서 작성해줘",
        "test-session",
        "device-1",
        ["assistant"],
    )
    state["has_documents"] = True

    result = await graph.ainvoke(state, config=_config("report"))

    assert result["completed_steps"] == ["assistant"]
    assert [tool_result["tool"] for tool_result in result["tool_results"]] == [
        "web_search",
        "retriever",
    ]
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_graph_assistant_answers_simple_query_without_tools():
    llm = CountingLLM()
    graph = build_graph(MockContainer(llm))
    state = create_initial_state(
        "안녕",
        "test-session",
        "device-1",
        ["assistant"],
    )

    result = await graph.ainvoke(state, config=_config("assistant"))

    assert result["completed_steps"] == ["assistant"]
    assert result["tool_results"] == []
    assert llm.calls == 1
