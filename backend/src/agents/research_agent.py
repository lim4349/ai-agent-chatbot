"""Research agent with agentic web and document evidence use."""

from typing import override

from dependency_injector.wiring import Provide, inject

from src.agents.base import BaseAgent
from src.agents.research_evidence import ResearchEvidenceCollector, ResearchToolDecision
from src.core.di_container import DIContainer
from src.core.protocols import LLMProvider, MemoryStore
from src.graph.state import AgentState
from src.observability import record_agent_metrics
from src.utils.message_utils import get_message_content, message_to_dict


class ResearchAgent(BaseAgent):
    """Agent for RAG, web search, and research/report synthesis."""

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "research"

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        memory: MemoryStore = Provide[DIContainer.memory],
        search_tool=None,
        retriever=None,
        metrics_store=Provide[DIContainer.metrics_store],
    ):
        super().__init__(llm, memory=memory)
        self.metrics_store = metrics_store
        self.evidence = ResearchEvidenceCollector(
            llm=llm,
            search_tool=search_tool,
            retriever=retriever,
        )

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for final research answers."""
        return """You are a research agent.

You answer using collected evidence from web search and uploaded documents.

Guidelines:
- Use uploaded-document context when the user asks about RAG, documents, files, or uploaded material.
- Use web context for current, latest, market, weather, news, or public web questions.
- If requested evidence is unavailable, say so clearly instead of inventing details.
- For report requests, produce a concise structured report with headings.
- Respond in the user's language."""

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Collect evidence and generate a final research answer."""
        session_id = state.get("metadata", {}).get("session_id", "default")
        user_id = state.get("metadata", {}).get("user_id")
        device_id = state.get("metadata", {}).get("device_id") or user_id
        query = get_message_content(state["messages"][-1])

        evidence = await self.evidence.collect(
            query=query,
            session_id=session_id,
            device_id=device_id,
            state=state,
        )

        messages = [{"role": "system", "content": self.system_prompt}]
        if self.memory:
            history = await self.memory.get_messages(session_id)
            messages.extend(history)

        messages.extend(message_to_dict(msg) for msg in state["messages"])
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Tool plan: {evidence.decision.reasoning or 'No additional reasoning.'}\n"
                    f"Response mode: {evidence.decision.response_mode}\n\n"
                    f"Collected context:\n{evidence.context or 'No tool context was collected.'}"
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
            response, usage = await self.llm.generate_with_usage(messages)
            metrics.set_token_count(usage.get("input_tokens", 0), usage.get("output_tokens", 0))

        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        workflow_updates = self._update_workflow_state(state, response)
        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            "tool_results": [*state.get("tool_results", []), *evidence.tool_results],
            **workflow_updates,
        }


__all__ = ["ResearchAgent", "ResearchToolDecision"]
