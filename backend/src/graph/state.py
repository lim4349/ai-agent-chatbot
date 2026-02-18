"""Agent state definition for LangGraph."""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Shared state across all agents in the graph.

    Attributes:
        messages: Conversation messages (uses add_messages reducer)
        next_agent: Agent selected by supervisor for routing
        tool_results: Accumulated tool execution results
        metadata: Session metadata (session_id, user_id, routing info)
    """

    messages: Annotated[list, add_messages]
    next_agent: str | None
    tool_results: list[dict[str, Any]]
    metadata: dict[str, Any]
    has_documents: bool


def create_initial_state(
    message: str, session_id: str = "default", device_id: str | None = None
) -> AgentState:
    """Create initial state for a new conversation.

    Args:
        message: User's message
        session_id: Session identifier
        device_id: Device identifier (guest mode)

    Returns:
        Initial AgentState
    """
    metadata = {"session_id": session_id}
    if device_id:
        metadata["device_id"] = device_id

    return {
        "messages": [{"role": "user", "content": message}],
        "next_agent": None,
        "tool_results": [],
        "metadata": metadata,
        "has_documents": False,
    }
