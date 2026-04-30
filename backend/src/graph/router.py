"""LLM router for selecting the active specialist agent."""

import re

from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.graph.state import AgentState

logger = get_logger(__name__)

ROUTABLE_AGENTS = {"chat", "research"}


class RouterDecision(BaseModel):
    """Structured routing decision returned by the LLM router."""

    agent: str = Field(..., description="Selected specialist agent: chat or research.")
    reasoning: str = Field(default="", description="Short reason for the route selection.")

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


def _with_agent(state: AgentState, agent: str) -> AgentState:
    """Set the next specialist agent."""
    return {"next_agent": agent}


def _latest_message_content(state: AgentState) -> str:
    """Return the latest message content from state."""
    messages = state.get("messages", [])
    if not messages:
        return ""
    last_msg = messages[-1]
    if isinstance(last_msg, dict):
        return str(last_msg.get("content", ""))
    return str(getattr(last_msg, "content", ""))


def _sanitize_agent(raw_agent: str, available_nodes: set[str]) -> str:
    """Keep the LLM route inside the compiled graph's valid agent set."""
    agent = str(raw_agent).strip()
    if agent in ROUTABLE_AGENTS and agent in available_nodes:
        return agent
    return "chat"


class LLMRouterNode:
    """Select the specialist agent with an LLM routing decision."""

    def __init__(self, llm) -> None:
        self.llm = llm

    async def __call__(self, state: AgentState) -> AgentState:
        """Route the request to chat or research."""
        content = _latest_message_content(state)
        available_nodes = set(state.get("available_nodes", [])) or {"chat"}
        if not content:
            return _with_agent(state, "chat")

        messages = [
            {
                "role": "system",
                "content": self._system_prompt(),
            },
            {
                "role": "user",
                "content": (
                    f"User message:\n{content}\n\n"
                    f"Available agents: {sorted(available_nodes & ROUTABLE_AGENTS)}\n"
                    f"has_documents: {state.get('has_documents', False)}"
                ),
            },
        ]

        try:
            decision = await self.llm.generate_structured(messages, output_schema=RouterDecision)
            if not decision:
                raise ValueError("LLM router returned no decision")
            agent = _sanitize_agent(decision.get("agent", ""), available_nodes)

            metadata = {
                **state.get("metadata", {}),
                "route_reasoning": decision.get("reasoning", ""),
                "route_source": "llm",
            }
            return {**_with_agent(state, agent), "metadata": metadata}
        except Exception as e:
            logger.warning("llm_router_failed_falling_back", error=str(e))
            fallback = await heuristic_route(state)
            return {
                **fallback,
                "metadata": {
                    **state.get("metadata", {}),
                    "route_reasoning": f"LLM router failed; heuristic fallback used: {e}",
                    "route_source": "heuristic_fallback",
                },
            }

    def _system_prompt(self) -> str:
        """Prompt that defines the routing contract."""
        return """You are a LangGraph routing agent.

Choose exactly one specialist agent for the user's request. Use only available agent names.

Available agent meanings:
- chat: general conversation, memory commands, ordinary Q&A.
- research: uploaded/RAG document questions, web/current information, source-grounded answers, research, analysis, and reports.

Routing rules:
- Memory commands such as 기억해, 알고 있니, 잊어줘, 요약해줘 go to chat.
- Explicit uploaded document/RAG/파일/문서/자료 questions go to research.
- Current/latest/news/weather/stock/price/search questions go to research.
- Report/synthesis/comprehensive analysis requests go to research.
- Programming/code questions go to chat unless they require external research.
- Use chat for ordinary conversation that does not require tools or evidence."""


async def heuristic_route(state: AgentState) -> AgentState:
    """Fallback heuristic routing node.

    Routes to the minimal specialist agent set based on keyword patterns in
    the last user message.

    Returns:
        Updated AgentState with next_agent set.
    """
    content = _latest_message_content(state)
    if not content:
        return _with_agent(state, "chat")

    available_nodes = set(state.get("available_nodes", []))

    # Code: no dedicated code agent in the minimal graph.
    if _CODE_PATTERNS.search(content):
        return _with_agent(state, "chat")

    # Research handles reports, web search, and uploaded document questions.
    if _REPORT_PATTERNS.search(content):
        return _with_agent(state, "research" if "research" in available_nodes else "chat")

    if _DOCUMENT_PATTERNS.search(content) or _WEB_SEARCH_PATTERNS.search(content):
        return _with_agent(state, "research" if "research" in available_nodes else "chat")

    return _with_agent(state, "chat")
