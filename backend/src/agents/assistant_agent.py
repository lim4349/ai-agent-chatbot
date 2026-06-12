"""Single assistant agent with optional research evidence use."""

from typing import override

from dependency_injector.wiring import Provide, inject

from src.agents.base import BaseAgent
from src.agents.conversation_memory import ConversationMemoryCommands
from src.agents.research_evidence import ResearchEvidenceCollector
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore, Summarizer, TopicMemory, UserProfiler
from src.graph.state import AgentState
from src.memory.long_term_memory import LongTermMemory
from src.observability import record_agent_metrics
from src.utils.message_utils import get_message_content, message_to_dict

logger = get_logger(__name__)


class AssistantAgent(BaseAgent):
    """User-facing assistant that owns conversation and evidence orchestration."""

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "assistant"

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        memory: MemoryStore = Provide[DIContainer.memory],
        long_term_memory: LongTermMemory | None = Provide[DIContainer.long_term_memory],
        user_profiler: UserProfiler | None = Provide[DIContainer.user_profiler],
        topic_memory: TopicMemory | None = Provide[DIContainer.topic_memory],
        summarizer: Summarizer | None = Provide[DIContainer.summarizer],
        search_tool=None,
        retriever=None,
        metrics_store=Provide[DIContainer.metrics_store],
    ):
        super().__init__(llm, memory=memory)
        self.long_term_memory = long_term_memory
        self.user_profiler = user_profiler
        self.topic_memory = topic_memory
        self.summarizer = summarizer
        self.metrics_store = metrics_store
        self.memory_commands = ConversationMemoryCommands(
            memory=memory,
            long_term_memory=long_term_memory,
            summarizer=summarizer,
        )
        self.evidence = ResearchEvidenceCollector(
            llm=llm,
            search_tool=search_tool,
            retriever=retriever,
        )
        self._user_profiles: dict[str, dict] = {}

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for the assistant."""
        return """You are a helpful AI assistant for an agentic RAG product.

Guidelines:
- Answer in the user's language.
- Use collected evidence when provided.
- If the evidence is missing, weak, or failed, say so clearly instead of inventing details.
- Cite uploaded-document or web context by source names when source metadata is available.
- Keep ordinary conversation concise and useful.

# CommonMark formatting rules

- Put every list item on its own line.
- Use "- " for unordered lists and "1. " style for ordered lists.
- Add blank lines before and after lists and headings.
"""

    async def process(self, state: AgentState) -> AgentState:
        """Handle memory commands, optional evidence collection, and final response."""
        session_id = state.get("metadata", {}).get("session_id", "default")
        user_id = state.get("metadata", {}).get("user_id")
        device_id = state.get("metadata", {}).get("device_id") or user_id
        query = get_message_content(state["messages"][-1])

        command = self.memory_commands.parse(query)
        if command.type != "none":
            response = await self.memory_commands.handle(session_id, user_id, command)
            if self.memory:
                await self.memory.add_message(session_id, message_to_dict(state["messages"][-1]))
                await self.memory.add_message(
                    session_id,
                    {"role": "assistant", "content": response},
                )
            workflow_updates = self._update_workflow_state(state, response or "")
            return {
                **state,
                "messages": [*state["messages"], {"role": "assistant", "content": response}],
                **workflow_updates,
            }

        evidence = await self.evidence.collect(
            query=query,
            session_id=session_id,
            device_id=device_id,
            state=state,
        )

        messages = [{"role": "system", "content": self.system_prompt}]
        if self.memory:
            messages.extend(await self.memory.get_messages(session_id))

        messages.extend(message_to_dict(msg) for msg in state["messages"])

        if evidence.context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Use the following Research Evidence when it is relevant.\n"
                        f"Response mode: {evidence.decision.response_mode}\n"
                        f"Evidence confidence: {evidence.confidence}\n"
                        f"Tool plan: {evidence.decision.reasoning or 'No additional reasoning.'}\n\n"
                        f"{evidence.context}"
                    ),
                }
            )

        async with record_agent_metrics(
            self.metrics_store,
            session_id,
            self.name,
            self.llm.config.model,
            user_id,
        ) as metrics:
            metrics.set_metadata(
                evidence_tools=[result.get("tool") for result in evidence.tool_results],
                evidence_confidence=evidence.confidence,
                evidence_count=evidence.evidence_count,
            )
            response, usage = await self.llm.generate_with_usage(messages)
            metrics.set_token_count(usage.get("input_tokens", 0), usage.get("output_tokens", 0))

        if self.memory:
            await self.memory.add_message(session_id, message_to_dict(state["messages"][-1]))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        workflow_updates = self._update_workflow_state(state, response)
        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            "tool_results": [*state.get("tool_results", []), *evidence.tool_results],
            **workflow_updates,
        }
