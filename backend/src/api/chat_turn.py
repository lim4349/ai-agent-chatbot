"""Chat turn intake helpers shared by sync and streaming routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.core.logging import log_request
from src.core.prompt_security import detect_injection, filter_llm_output, sanitize_for_llm
from src.core.protocols import DocumentRetriever, SessionStore
from src.graph.state import AgentState, create_initial_state
from src.tools.registry import ToolRegistry
from src.utils.message_utils import get_message_content


@dataclass(frozen=True)
class ChatTurn:
    """Prepared chat turn ready for LangGraph execution."""

    sanitized_message: str
    device_id: str | None
    has_documents: bool
    available_nodes: list[str]
    initial_state: AgentState
    graph_config: dict[str, Any]


class PromptInjectionRejectedError(ValueError):
    """Raised when a chat message violates prompt-security rules."""


def get_graph_capabilities(
    tool_registry: ToolRegistry | None,
    retriever: DocumentRetriever | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Return available agent nodes, tools, and routable graph nodes."""
    agent_nodes = ["chat", "research"]

    available_tools = []
    if tool_registry and tool_registry.get("web_search"):
        available_tools.append("web_search")
    if retriever or (tool_registry and tool_registry.get("retriever")):
        available_tools.append("retriever")

    return agent_nodes, available_tools, agent_nodes


def validate_and_sanitize_message(message: str, session_id: str, path: str) -> str:
    """Apply prompt-security checks and return sanitized message text."""
    injection = detect_injection(message)
    if injection:
        log_request(
            method="POST",
            path=path,
            session_id=session_id,
            user_message=message,
            duration_ms=0,
            status="blocked",
            error=f"Prompt injection detected: {injection['type']}",
        )
        raise PromptInjectionRejectedError("Invalid request. Please try again with different input.")

    return sanitize_for_llm(message)


async def prepare_chat_turn(
    *,
    sanitized_message: str,
    session_id: str,
    request_device_id: str | None,
    path: str,
    vector_store: Any,
    session_store: SessionStore | None,
    tool_registry: ToolRegistry | None,
) -> ChatTurn:
    """Resolve session context and create the initial LangGraph state."""
    device_id = request_device_id
    has_docs = False

    if session_store:
        try:
            session = await session_store.get(session_id)
            if session:
                if not device_id:
                    device_id = session.user_id
                if vector_store:
                    has_docs = await vector_store.has_documents_for_session(
                        device_id=device_id,
                        session_id=session_id,
                    )
        except Exception as e:
            log_request(
                method="POST",
                path=path,
                session_id=session_id,
                user_message="[session_store unavailable]",
                duration_ms=0,
                status="warning",
                error=f"Session store error (continuing without session): {e}",
            )

    _, _, available_nodes = get_graph_capabilities(tool_registry)
    initial_state = create_initial_state(
        sanitized_message,
        session_id,
        device_id,
        available_nodes,
    )
    initial_state["has_documents"] = has_docs

    return ChatTurn(
        sanitized_message=sanitized_message,
        device_id=device_id,
        has_documents=has_docs,
        available_nodes=available_nodes,
        initial_state=initial_state,
        graph_config={"configurable": {"thread_id": f"{session_id}:{uuid4()}"}},
    )


def extract_response_message(result: dict[str, Any]) -> str:
    """Extract and filter the assistant response from a graph result."""
    messages = result.get("messages", [])
    response_message = get_message_content(messages[-1]) if messages else ""
    return filter_llm_output(response_message)


def resolve_agent_used(result: dict[str, Any]) -> str:
    """Determine which specialist agent actually processed the request."""
    completed_steps = result.get("completed_steps", [])
    if completed_steps:
        return completed_steps[-1]

    agent_used = result.get("next_agent", "chat")
    if agent_used == "done":
        return "chat"
    return agent_used or "chat"
