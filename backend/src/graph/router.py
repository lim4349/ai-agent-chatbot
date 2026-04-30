"""LLM router with a heuristic fallback."""

import re
from typing import Any

from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.graph.state import AgentState
from src.graph.task_queue import set_task_queue

logger = get_logger(__name__)

ROUTABLE_NODES = {
    "chat",
    "code",
    "rag",
    "report",
    "web_search_collect",
    "retriever_collect",
}
TERMINAL_AGENTS = {"chat", "code", "rag", "report"}


class RouterDecision(BaseModel):
    """Structured routing decision returned by the LLM router."""

    tasks: list[str] = Field(
        ...,
        description=(
            "Ordered LangGraph task queue. Use only routable node names such as "
            "chat, code, rag, report, web_search_collect, retriever_collect."
        ),
    )
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


def _with_tasks(state: AgentState, tasks: list[str]) -> AgentState:
    """Set task queue and clear legacy tool hints."""
    return {**set_task_queue(state, tasks), "tools_hint": []}


def _latest_message_content(state: AgentState) -> str:
    """Return the latest message content from state."""
    messages = state.get("messages", [])
    if not messages:
        return ""
    last_msg = messages[-1]
    if isinstance(last_msg, dict):
        return str(last_msg.get("content", ""))
    return str(getattr(last_msg, "content", ""))


def _sanitize_tasks(raw_tasks: list[Any], available_nodes: set[str]) -> list[str]:
    """Keep the LLM route inside the compiled graph's valid node set."""
    tasks = []
    for task in raw_tasks:
        task_name = str(task).strip()
        if task_name in ROUTABLE_NODES and task_name in available_nodes and task_name not in tasks:
            tasks.append(task_name)

    if not tasks:
        return []

    # Ensure the queue terminates at a response-producing agent.
    terminal_index = next((idx for idx, task in enumerate(tasks) if task in TERMINAL_AGENTS), None)
    if terminal_index is None:
        tasks.append("chat" if "chat" in available_nodes else next(iter(available_nodes), "chat"))
    else:
        tasks = tasks[: terminal_index + 1]

    if "rag" in tasks and "retriever_collect" in available_nodes and "retriever_collect" not in tasks:
        tasks.insert(0, "retriever_collect")

    return tasks


class LLMRouterNode:
    """Create the graph task queue with an LLM routing decision."""

    def __init__(self, llm) -> None:
        self.llm = llm

    async def __call__(self, state: AgentState) -> AgentState:
        """Route the request to deterministic tool nodes and one specialist agent."""
        content = _latest_message_content(state)
        available_nodes = set(state.get("available_nodes", [])) or {"chat"}
        if not content:
            return _with_tasks(state, ["chat"])

        messages = [
            {
                "role": "system",
                "content": self._system_prompt(),
            },
            {
                "role": "user",
                "content": (
                    f"User message:\n{content}\n\n"
                    f"Available graph nodes: {sorted(available_nodes)}\n"
                    f"has_documents: {state.get('has_documents', False)}"
                ),
            },
        ]

        try:
            decision = await self.llm.generate_structured(messages, output_schema=RouterDecision)
            if not decision:
                raise ValueError("LLM router returned no decision")
            tasks = _sanitize_tasks(decision.get("tasks", []), available_nodes)
            if not tasks:
                raise ValueError(f"LLM router returned no valid tasks: {decision}")

            metadata = {
                **state.get("metadata", {}),
                "route_reasoning": decision.get("reasoning", ""),
                "route_source": "llm",
            }
            return {**_with_tasks(state, tasks), "metadata": metadata}
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

Return an ordered task queue for the user's request. Use only available graph node names.

Available node meanings:
- chat: general conversation, memory commands, ordinary Q&A.
- code: programming, debugging, code review, algorithms, shell/SQL/code-related tasks.
- web_search_collect: collect current/public web context without answering.
- retriever_collect: collect uploaded/RAG document context without answering.
- rag: answer using uploaded/RAG document context.
- report: synthesize collected context into a structured report.

Routing rules:
- Memory commands such as 기억해, 알고 있니, 잊어줘, 요약해줘 go to chat.
- Explicit uploaded document/RAG/파일/문서/자료 questions go to retriever_collect then rag, even if has_documents is false.
- Current/latest/news/weather/stock/price/search questions go to web_search_collect then chat, unless they explicitly ask about uploaded/RAG documents.
- Code/programming questions go to code.
- Report/synthesis/comprehensive analysis requests go to report. Add web_search_collect first when current web context is useful and available. Add retriever_collect before report when uploaded/RAG document context is requested or has_documents is true.
- Choose exactly one final answer agent: chat, code, rag, or report.
- Do not include router or END in tasks."""


async def heuristic_route(state: AgentState) -> AgentState:
    """Fallback heuristic routing node.

    Routes to specialist agents and deterministic tool nodes based on keyword
    patterns in the last user message.

    Returns:
        Updated AgentState with next_agent and tools_hint set.
    """
    content = _latest_message_content(state)
    if not content:
        return _with_tasks(state, ["chat"])

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
    # Do this even when has_documents is false so explicit RAG/document queries
    # do not fall through to web search because of words like "지금" or "현재".
    if (
        _DOCUMENT_PATTERNS.search(content)
        and "retriever_collect" in available_nodes
        and "rag" in available_nodes
    ):
        return _with_tasks(state, ["retriever_collect", "rag"])

    # Current information: collect web search results, then chat over them.
    if _WEB_SEARCH_PATTERNS.search(content) and "web_search_collect" in available_nodes:
        return _with_tasks(state, ["web_search_collect", "chat"])

    return _with_tasks(state, ["chat"])
