"""Supervisor agent for routing user queries to specialist agents."""

import re
from typing import Literal, override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.core.container import Container
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore, MemoryTool
from src.graph.state import AgentState

logger = get_logger(__name__)


def message_to_dict(msg) -> dict:
    """Convert LangChain message to dict format."""
    if isinstance(msg, dict):
        return msg
    if isinstance(msg, BaseMessage):
        return {"role": msg.type, "content": msg.content}
    return {"role": "user", "content": str(msg)}


# Agent descriptions for dynamic prompt generation
AGENT_DESCRIPTIONS = {
    "rag": "For questions about uploaded documents, knowledge bases, or when the user needs information from stored documents. Use when the query might be answered by internal knowledge.",
    "web_search": "For real-time information, current events, weather, news, latest technology updates, or anything requiring up-to-date information from the internet.",
    "code": "For code writing, debugging, code explanation, algorithm implementation, programming questions, or any task involving programming languages.",
    "chat": "For general conversation, greetings, casual questions, opinions, creative writing, or any query that doesn't fit the other categories.",
}


def create_route_decision_model(available_agents: set[str]):
    """Create a RouteDecision model with dynamic agent choices."""
    agent_literal = Literal[tuple(available_agents)]  # type: ignore

    class SupervisorRoutingDecision(BaseModel):
        """Supervisor's decision for routing user queries to specialist agents."""
        selected_agent: agent_literal = Field(
            description="The name of the agent to route the query to"
        )
        reasoning: str = Field(description="Brief explanation of why this agent was selected")

    return SupervisorRoutingDecision


class SupervisorAgent(BaseAgent):
    """Supervisor agent that routes queries to specialist agents."""

    _system_prompt: str = ""  # Instance attribute for dynamic prompt

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "supervisor"

    # Korean reference patterns for memory-aware routing
    REFERENCE_PATTERNS = [
        r"이전에",
        r"그것",
        r"그거",
        r"그 코드",
        r"그 함수",
        r"그 파일",
        r"방금",
        r"아까",
        r"전에",
        r"위에서",
        r"앞에서",
        r"말한",
        r"얘기한",
        r"질문한",
    ]

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[Container.llm],
        available_agents: set[str] | None = None,
        memory: MemoryStore = Provide[Container.memory],
        memory_tool: MemoryTool | None = Provide[Container.memory_tool],
    ):
        """Initialize supervisor with LLM and available agents.

        Args:
            llm: The LLM to use for routing decisions
            available_agents: Set of available agent names (e.g., {'chat', 'code', 'rag'})
            memory: Optional memory store for conversation history
            memory_tool: Optional memory tool for semantic search
        """
        super().__init__(llm=llm, memory=memory)
        # Default to all agents if not specified
        self.available_agents = available_agents or {"chat", "code", "rag", "web_search"}
        # Ensure 'chat' is always available as fallback
        self.available_agents.add("chat")
        self.memory_tool = memory_tool
        self._build_system_prompt()

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        return self._system_prompt

    def _build_system_prompt(self):
        """Build system prompt based on available agents."""
        agent_list = []
        for agent in sorted(self.available_agents):
            if agent in AGENT_DESCRIPTIONS:
                agent_list.append(f"- {agent}: {AGENT_DESCRIPTIONS[agent]}")

        self._system_prompt = f"""You are a supervisor that analyzes user queries and routes them to the most appropriate specialist agent.

Available agents:
{chr(10).join(agent_list)}

Analyze the user's intent and select the SINGLE most appropriate agent.
Consider the context of the conversation when making your decision."""

    def _contains_reference_to_previous(self, content: str) -> bool:
        """Check if query contains references to previous conversation.

        Args:
            content: The user query content

        Returns:
            True if query refers to previous conversation
        """
        content_lower = content.lower()

        for pattern in self.REFERENCE_PATTERNS:
            if re.search(pattern, content_lower):
                logger.debug("reference_pattern_matched", pattern=pattern, content=content[:50])
                return True

        return False

    async def _resolve_ambiguous_reference(
        self, session_id: str, content: str
    ) -> list[dict] | None:
        """Resolve ambiguous references using memory search.

        Args:
            session_id: The session identifier
            content: The user query with ambiguous reference

        Returns:
            List of relevant context messages or None
        """
        if not self.memory_tool:
            return None

        try:
            # Search for relevant context
            results = await self.memory_tool.search_memory(
                query=content, session_id=session_id, top_k=3
            )

            if results:
                logger.info(
                    "resolved_reference",
                    session_id=session_id,
                    results_count=len(results),
                )
                return [r["message"] for r in results]

        except Exception as e:
            logger.error("reference_resolution_failed", error=str(e), session_id=session_id)

        return None

    async def _get_memory_enriched_context(
        self, session_id: str, messages: list[dict]
    ) -> list[dict]:
        """Get conversation context enriched with relevant memories.

        Args:
            session_id: The session identifier
            messages: Current messages

        Returns:
            Enriched context messages
        """
        if not messages:
            return []

        # Get the last user message
        last_message = messages[-1]
        content = last_message.get("content", "")

        # Check if it contains ambiguous references
        if not self._contains_reference_to_previous(content):
            return []

        # Try to resolve the reference
        context = await self._resolve_ambiguous_reference(session_id, content)

        if context:
            # Add context marker
            context.insert(
                0,
                {
                    "role": "system",
                    "content": "[Relevant context from previous conversation]",
                },
            )
            return context

        return []

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Analyze query and determine routing."""
        session_id = state.get("metadata", {}).get("session_id", "default")

        messages = [{"role": "system", "content": self.system_prompt}]

        # Include conversation history if memory is available
        if self.memory:
            history = await self.memory.get_messages(session_id)
            messages.extend(history)

        # Check for ambiguous references and enrich context
        current_messages = [message_to_dict(msg) for msg in state["messages"]]
        enriched_context = await self._get_memory_enriched_context(
            session_id, current_messages
        )
        if enriched_context:
            messages.extend(enriched_context)
            logger.info(
                "enriched_context_added",
                session_id=session_id,
                context_messages=len(enriched_context),
            )

        # Convert LangChain messages to dict format
        for msg in state["messages"]:
            messages.append(message_to_dict(msg))

        # Get structured routing decision with dynamic model
        route_decision = create_route_decision_model(self.available_agents)
        decision = await self.llm.generate_structured(
            messages=messages,
            output_schema=route_decision,
        )

        # Handle None response from LLM (fallback to chat)
        if not decision:
            logger.warning("supervisor_llm_returned_none", session_id=session_id)
            decision = {"selected_agent": "chat", "reasoning": "LLM response was empty, defaulting to chat"}

        # Store the routing exchange in memory if available
        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(
                session_id,
                {
                    "role": "assistant",
                    "content": f"Routing to: {decision['selected_agent']} (reasoning: {decision['reasoning']})",
                },
            )

        return {
            **state,
            "next_agent": decision["selected_agent"],
            "metadata": {
                **state.get("metadata", {}),
                "route_reasoning": decision["reasoning"],
            },
        }
