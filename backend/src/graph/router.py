"""Heuristic router — routes queries without any LLM call."""

import re

from src.graph.state import AgentState

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


async def heuristic_route(state: AgentState) -> AgentState:
    """Heuristic routing node — sets next_agent and tools_hint, no LLM.

    Routes to the appropriate agent based on keyword patterns in the last
    user message.  Mutates state as a LangGraph node (returns updated dict).

    Returns:
        Updated AgentState with next_agent and tools_hint set.
    """
    messages = state.get("messages", [])
    if not messages:
        return {**state, "next_agent": "chat", "tools_hint": []}

    last_msg = messages[-1]
    if isinstance(last_msg, dict):
        content = last_msg.get("content", "")
    else:
        content = getattr(last_msg, "content", "")

    has_documents = state.get("has_documents", False)
    available_agents = set(state.get("available_agents", []))

    # Code: route to dedicated code agent
    if _CODE_PATTERNS.search(content):
        if "code" not in available_agents:
            return {**state, "next_agent": "chat", "tools_hint": []}
        return {**state, "next_agent": "code", "tools_hint": []}

    # Report: complex multi-source synthesis (pre-fetch web search)
    if _REPORT_PATTERNS.search(content):
        return {**state, "next_agent": "report", "tools_hint": ["web_search"]}

    # Chat: determine which tools to pre-fetch
    tools_hint: list[str] = []
    if _WEB_SEARCH_PATTERNS.search(content):
        tools_hint.append("web_search")
    if has_documents:
        tools_hint.append("retriever")

    return {**state, "next_agent": "chat", "tools_hint": tools_hint}
