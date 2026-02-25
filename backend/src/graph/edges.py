"""Conditional edges for LangGraph routing."""

from typing import Literal

from src.graph.state import AgentState


def route_by_next_agent(
    state: AgentState,
) -> Literal["rag", "web_search", "code", "chat", "report", "__end__"]:
    """Route based on supervisor's decision.

    Args:
        state: Current graph state

    Returns:
        Name of the next agent node or "__end__" if workflow is complete
    """
    next_agent = state.get("next_agent")

    if next_agent is None or next_agent == "done":
        return "__end__"

    # Validate the agent name
    valid_agents = {"rag", "web_search", "code", "chat", "report"}
    if next_agent not in valid_agents:
        return "chat"

    return next_agent


def route_after_agent(
    state: AgentState,
) -> Literal["supervisor", "__end__"]:
    """Route after specialist agent completes.

    Optimization: Skip supervisor call if no remaining tasks.
    This reduces LLM calls from 3 to 2 for simple single-step queries.

    Args:
        state: Current graph state

    Returns:
        "supervisor" if there are remaining tasks, "__end__" otherwise
    """
    remaining_tasks = state.get("remaining_tasks", [])

    # If there are remaining tasks, go back to supervisor for next step
    if remaining_tasks:
        return "supervisor"

    # No remaining tasks - workflow is complete, skip supervisor call
    return "__end__"
