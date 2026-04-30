"""Conditional edges for LangGraph routing."""

from typing import Literal

from src.graph.state import AgentState

GraphRoute = Literal[
    "chat",
    "research",
    "__end__",
]


def route_to_next_task(state: AgentState) -> GraphRoute:
    """Route to the next queued graph task."""
    next_agent = state.get("next_agent", "chat")
    valid = {"chat", "research"}
    if not next_agent:
        return "__end__"
    if next_agent not in valid:
        return "chat"
    return next_agent
