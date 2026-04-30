"""Helpers for LangGraph task-queue based routing."""

from typing import Any

from src.graph.state import AgentState


def set_task_queue(state: AgentState, tasks: list[str]) -> AgentState:
    """Set the graph task queue and select the first task."""
    clean_tasks = [task for task in tasks if task]
    return {
        "next_agent": clean_tasks[0] if clean_tasks else None,
        "remaining_tasks": clean_tasks,
    }


def complete_task(
    state: AgentState,
    step_name: str,
    result_content: str | None = None,
    tool_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark the current task complete and advance to the next queued task."""
    remaining_tasks = list(state.get("remaining_tasks", []))
    if remaining_tasks and remaining_tasks[0] == step_name:
        remaining_tasks.pop(0)
    elif step_name in remaining_tasks:
        remaining_tasks.remove(step_name)

    completed_steps = list(state.get("completed_steps", []))
    if step_name not in completed_steps:
        completed_steps.append(step_name)

    workflow_context = state.get("workflow_context", "")
    if result_content:
        workflow_context += f"\n<<<STEP:{step_name}>>>\n{result_content[:2000]}\n<<<END>>>"

    updates: dict[str, Any] = {
        "next_agent": remaining_tasks[0] if remaining_tasks else None,
        "remaining_tasks": remaining_tasks,
        "completed_steps": completed_steps,
        "workflow_context": workflow_context,
    }

    if tool_result is not None:
        updates["tool_results"] = [*state.get("tool_results", []), tool_result]

    return updates
