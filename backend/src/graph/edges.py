"""Conditional edges for LangGraph routing."""

from typing import Literal

from src.graph.state import AgentState


def route_from_router(state: AgentState) -> Literal["chat", "code", "report", "__end__"]:
    """Route based on heuristic router's decision (next_agent field)."""
    next_agent = state.get("next_agent", "chat")
    valid = {"chat", "code", "report"}
    if next_agent not in valid:
        return "chat"
    return next_agent
