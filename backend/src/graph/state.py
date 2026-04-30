"""Agent state definition for LangGraph."""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Shared state across all agents in the graph.

    Attributes:
        messages: Conversation messages (uses add_messages reducer)
        next_agent: Next graph task selected by the LLM router
        tool_results: Accumulated tool execution results
        metadata: Session metadata (session_id, user_id, routing info)
        has_documents: Whether documents are available for RAG
        completed_steps: List of completed agent names in current workflow
        workflow_context: Accumulated context from previous steps
        available_nodes: Available graph agent names for capability awareness
    """

    messages: Annotated[list, add_messages]
    next_agent: str | None
    tool_results: list[dict[str, Any]]
    metadata: dict[str, Any]
    has_documents: bool
    completed_steps: list[str]
    workflow_context: str
    available_nodes: list[str]


def create_initial_state(
    message: str,
    session_id: str = "default",
    device_id: str | None = None,
    available_nodes: list[str] | None = None,
) -> AgentState:
    """Create initial state for a new conversation.

    Args:
        message: User's message
        session_id: Session identifier
        device_id: Device identifier (guest mode) - also used as user_id for cross-session continuity
        available_nodes: List of available graph agent names

    Returns:
        Initial AgentState
    """
    metadata = {"session_id": session_id}
    if device_id:
        metadata["device_id"] = device_id
        metadata["user_id"] = device_id  # Use device_id as user_id for cross-session continuity

    return {
        "messages": [{"role": "user", "content": message}],
        "next_agent": None,
        "tool_results": [],
        "metadata": metadata,
        "has_documents": False,
        "completed_steps": [],
        "workflow_context": "",
        "available_nodes": available_nodes or ["chat", "research"],
    }
