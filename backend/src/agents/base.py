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
