"""Heuristic router — routes queries without any LLM call."""

import re

from src.graph.state import AgentState
from src.graph.task_queue import set_task_queue

# Keyword patterns
_CODE_PATTERNS = re.compile(
    r"\b(코드|code|python|javascript|typescript|함수|function|알고리즘|algorithm|"
    r"debug|디버그|오류|에러|error|bug|실행|run|execute|구현|implement|"
    r"sql|bash|shell|script|class|def |import |print\()\b",
    re.IGNORECASE,
)

_REPORT_PATTERNS = re.compile(
    r"\b(리포트|보고서|report|종합|분석 보고서|전체 분석|summarize all|"
    r"comprehensive|체계적으로 정리|상세 보고|detailed report)\b",
    re.IGNORECASE,
)

_WEB_SEARCH_PATTERNS = re.compile(
    r"\b(검색|찾아|알려줘|최신|현재|지금|오늘|최근|뉴스|news|날씨|weather|"
    r"주가|가격|price|환율|real.?time|실시간|search|find|what is|what are|"
    r"how to|how do|언제|어디서|누가|몇 시|몇 월)\b",
    re.IGNORECASE,
)

_DOCUMENT_PATTERNS = re.compile(
    r"(문서|자료|파일|업로드|pdf|docx|document|documents|file|knowledge base|"
    r"지식\s*베이스|첨부|근거|reference|references)",
    re.IGNORECASE,
)


def _with_tasks(state: AgentState, tasks: list[str]) -> AgentState:
    """Set task queue and clear legacy tool hints."""
    return {**set_task_queue(state, tasks), "tools_hint": []}


async def heuristic_route(state: AgentState) -> AgentState:
    """Heuristic routing node — sets the graph task queue, no LLM.

    Routes to specialist agents and deterministic tool nodes based on keyword
    patterns in the last user message.

    Returns:
        Updated AgentState with next_agent and tools_hint set.
    """
    messages = state.get("messages", [])
    if not messages:
        return _with_tasks(state, ["chat"])

    last_msg = messages[-1]
    if isinstance(last_msg, dict):
        content = last_msg.get("content", "")
    else:
        content = getattr(last_msg, "content", "")

    has_documents = state.get("has_documents", False)
    available_nodes = set(state.get("available_nodes", []))

    # Code: route to dedicated code agent when available.
    if _CODE_PATTERNS.search(content):
        return _with_tasks(state, ["code"] if "code" in available_nodes else ["chat"])

    # Report: collect available external context, then synthesize once.
    if _REPORT_PATTERNS.search(content):
        tasks: list[str] = []
        if "web_search_collect" in available_nodes:
            tasks.append("web_search_collect")
        if has_documents and "retriever_collect" in available_nodes:
            tasks.append("retriever_collect")
        tasks.append("report")
        return _with_tasks(state, tasks)

    # Document-grounded answer: retrieve first, then answer with RAG agent.
    if has_documents and _DOCUMENT_PATTERNS.search(content) and "retriever_collect" in available_nodes:
        return _with_tasks(state, ["retriever_collect", "rag"])

    # Current information: collect web search results, then chat over them.
    if _WEB_SEARCH_PATTERNS.search(content) and "web_search_collect" in available_nodes:
        return _with_tasks(state, ["web_search_collect", "chat"])

    return _with_tasks(state, ["chat"])
