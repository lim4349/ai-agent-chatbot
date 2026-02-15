"""Conditional edges for LangGraph routing."""

from typing import Literal

from src.graph.state import AgentState


def route_by_next_agent(state: AgentState) -> Literal["rag", "web_search", "code", "chat"]:
    """Route based on supervisor's decision.

    Args:
        state: Current graph state

    Returns:
        Name of the next agent node
    """
    next_agent = state.get("next_agent")

    if next_agent is None:
        return "chat"

    # Validate the agent name
    valid_agents = {"rag", "web_search", "code", "chat"}
    if next_agent not in valid_agents:
        return "chat"

    return next_agent
