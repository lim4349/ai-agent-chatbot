"""Factory for creating agent instances."""

from src.core.protocols import LLMProvider, MemoryStore


class AgentFactory:
    """Factory for creating agent instances."""

    @staticmethod
    def create_assistant(
        llm: LLMProvider,
        memory: MemoryStore,
        long_term_memory,
        user_profiler,
        topic_memory,
        summarizer,
        search_tool=None,
        retriever=None,
    ):
        """Create the user-facing assistant agent."""
        from src.agents.assistant_agent import AssistantAgent

        return AssistantAgent(
            llm=llm,
            memory=memory,
            long_term_memory=long_term_memory,
            user_profiler=user_profiler,
            topic_memory=topic_memory,
            summarizer=summarizer,
            search_tool=search_tool,
            retriever=retriever,
        )
