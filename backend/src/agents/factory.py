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
        search_tool=None,
        retriever=None,
    ):
        """Create chat agent instance.

        Args:
            llm: LLM provider
            memory: Memory store
            long_term_memory: Long-term memory (optional)
            user_profiler: User profiler (optional)
            topic_memory: Topic memory (optional)
            summarizer: Summarizer (optional)
            search_tool: Web search tool (optional)
            retriever: Document retriever tool (optional)

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
            search_tool=search_tool,
            retriever=retriever,
        )

    @staticmethod
    def create_code(
        llm: LLMProvider,
        memory: MemoryStore,
        tool_registry,
    ):
        """Create code agent instance.

        Args:
            llm: LLM provider
            memory: Memory store
            tool_registry: Tool registry

        Returns:
            CodeAgent instance or None if code_executor not available
        """
        from src.agents.code_agent import CodeAgent

        code_executor = tool_registry.get("code_executor") if tool_registry else None
        if not code_executor:
            return None
        return CodeAgent(
            llm=llm,
            code_executor=code_executor,
            memory=memory,
        )

    @staticmethod
    def create_report(
        llm: LLMProvider,
        memory: MemoryStore,
        search_tool=None,
        retriever=None,
    ):
        """Create report agent instance.

        Args:
            llm: LLM provider
            memory: Memory store
            search_tool: Web search tool (optional)
            retriever: Document retriever tool (optional)

        Returns:
            ReportAgent instance
        """
        from src.agents.report_agent import ReportAgent

        return ReportAgent(
            llm=llm,
            memory=memory,
            search_tool=search_tool,
            retriever=retriever,
        )
