"""Deterministic LangGraph tool nodes."""

from typing import Any

from src.core.logging import get_logger
from src.graph.state import AgentState
from src.graph.task_queue import complete_task

logger = get_logger(__name__)


def get_latest_user_content(state: AgentState) -> str:
    """Extract the latest user message content from graph state."""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "type", getattr(msg, "role", None))
            content = getattr(msg, "content", "")
        if role in ("user", "human") and content:
            return str(content)
    return ""


def format_retrieved_documents(docs: list[dict[str, Any]]) -> str:
    """Format retrieved document chunks for downstream agents."""
    return "\n\n".join(
        f"[{doc.get('metadata', {}).get('source') or doc.get('metadata', {}).get('filename') or 'doc'}]\n"
        f"{doc.get('content', '')}"
        for doc in docs
        if isinstance(doc, dict)
    )


class WebSearchCollectNode:
    """Collect web search results without an LLM call."""

    def __init__(self, search_tool=None) -> None:
        self.search_tool = search_tool

    async def __call__(self, state: AgentState) -> AgentState:
        query = get_latest_user_content(state)
        result_text = ""
        tool_result: dict[str, Any] = {"tool": "web_search", "query": query, "results": ""}

        if not self.search_tool:
            tool_result["error"] = "web_search tool is not configured"
            logger.info("web_search_collect_skipped", reason="tool_not_configured")
        else:
            try:
                result_text = await self.search_tool.execute(query)
                tool_result["results"] = result_text
            except Exception as e:
                tool_result["error"] = str(e)
                logger.warning("web_search_collect_failed", error=str(e))

        return complete_task(
            state,
            "web_search_collect",
            result_text or tool_result.get("error"),
            tool_result,
        )


class RetrieverCollectNode:
    """Collect relevant document chunks without an LLM call."""

    def __init__(self, retriever_tool=None) -> None:
        self.retriever_tool = retriever_tool

    async def __call__(self, state: AgentState) -> AgentState:
        query = get_latest_user_content(state)
        metadata = state.get("metadata", {})
        session_id = metadata.get("session_id", "default")
        device_id = metadata.get("device_id") or metadata.get("user_id")
        docs: list[dict[str, Any]] = []
        docs_text = ""
        tool_result: dict[str, Any] = {"tool": "retriever", "query": query, "results": docs}

        if not self.retriever_tool:
            tool_result["error"] = "retriever tool is not configured"
            logger.info("retriever_collect_skipped", reason="tool_not_configured")
        elif not state.get("has_documents"):
            tool_result["error"] = "no documents are available for this session"
            logger.info("retriever_collect_skipped", reason="no_documents")
        else:
            try:
                docs = await self.retriever_tool.execute(
                    query,
                    top_k=3,
                    session_id=session_id,
                    device_id=device_id,
                )
                docs_text = format_retrieved_documents(docs)
                tool_result["results"] = docs
            except Exception as e:
                tool_result["error"] = str(e)
                logger.warning("retriever_collect_failed", error=str(e))

        return complete_task(
            state,
            "retriever_collect",
            docs_text or tool_result.get("error"),
            tool_result,
        )
