"""Base agent abstract class."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.graph.state import AgentState


class BaseAgent(ABC):
    """Base class for all agents.

    - LLM dependency injected via constructor
    - System prompt and tools defined as properties
    - Can be converted to LangGraph node function
    """

    def __init__(self, llm, tools: list | None = None, memory=None):
        self.llm = llm
        self.tools = tools or []
        self.memory = memory

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent identifier."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        ...

    @abstractmethod
    async def process(self, state: "AgentState") -> "AgentState":
        """Process state and return updated state.

        Used directly as LangGraph node function.
        """
        ...

    def as_node(self):
        """Convert to LangGraph node function."""
        return self.process

    def _update_workflow_state(
        self,
        state: "AgentState",
        result_content: str,
    ) -> dict:
        """Update workflow state after agent execution.

        Call this at the end of each agent's process method to track
        completed steps and accumulate context for multi-step workflows.

        Args:
            state: Current agent state
            result_content: The content produced by this agent

        Returns:
            Dict with updated completed_steps and workflow_context
        """
        completed_steps = list(state.get("completed_steps", []))
        workflow_context = state.get("workflow_context", "")

        # Add this agent to completed steps
        if self.name not in completed_steps:
            completed_steps.append(self.name)

        # Append result to workflow context (for next steps)
        if result_content:
            new_context = f"\n[{self.name}]: {result_content[:1000]}"
            workflow_context = workflow_context + new_context

        return {
            "completed_steps": completed_steps,
            "workflow_context": workflow_context,
        }
