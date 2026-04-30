"""Factory for creating agent instances."""

from src.core.protocols import LLMProvider, MemoryStore


class AgentFactory:
    """Factory for creating agent instances."""

    @staticmethod
    def create_chat(
        llm: LLMProvider,
        memory: MemoryStore,
        long_term_memory,
        user_profiler,
        topic_memory,
        summarizer,
    ):
        """Create chat agent instance.

        Args:
            llm: LLM provider
            memory: Memory store
            long_term_memory: Long-term memory (optional)
            user_profiler: User profiler (optional)
            topic_memory: Topic memory (optional)
            summarizer: Summarizer (optional)
        Returns:
            ChatAgent instance
        """
        from src.agents.chat_agent import ChatAgent

        return ChatAgent(
            llm=llm,
            memory=memory,
            long_term_memory=long_term_memory,
            user_profiler=user_profiler,
            topic_memory=topic_memory,
            summarizer=summarizer,
        )

    @staticmethod
    def create_research(
        llm: LLMProvider,
        memory: MemoryStore,
        search_tool=None,
        retriever=None,
    ):
        """Create research agent instance.

        Args:
            llm: LLM provider
            memory: Memory store
            search_tool: Web search tool (optional)
            retriever: Document retriever tool (optional)

        Returns:
            ResearchAgent instance
        """
        from src.agents.research_agent import ResearchAgent

        return ResearchAgent(
            llm=llm,
            memory=memory,
            search_tool=search_tool,
            retriever=retriever,
        )
