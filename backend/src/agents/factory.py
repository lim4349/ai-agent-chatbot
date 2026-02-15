"""Factory for creating agent instances."""

from typing import Optional

from src.core.protocols import LLMProvider, MemoryStore, DocumentRetriever


class AgentFactory:
    """Factory for creating agent instances."""

    @staticmethod
    def create_supervisor(
        llm: LLMProvider,
        memory: MemoryStore,
        retriever: Optional[DocumentRetriever],
        tool_registry,
        memory_tool,
    ):
        """Create supervisor agent instance.

        Args:
            llm: LLM provider
            memory: Memory store
            retriever: Document retriever (optional)
            tool_registry: Tool registry
            memory_tool: Memory tool

        Returns:
            SupervisorAgent instance
        """
        from src.agents.supervisor import SupervisorAgent

        available_agents = {"chat", "code"}
        if retriever:
            available_agents.add("rag")
        if tool_registry and tool_registry.get("web_search"):
            available_agents.add("web_search")

        return SupervisorAgent(
            llm=llm,
            available_agents=available_agents,
            memory=memory,
            memory_tool=memory_tool,
        )

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
            CodeAgent instance
        """
        from src.agents.code_agent import CodeAgent

        code_executor = tool_registry.get("code_executor") if tool_registry else None
        return CodeAgent(
            llm=llm,
            code_executor=code_executor,
            memory=memory,
        )

    @staticmethod
    def create_rag(
        llm: LLMProvider,
        memory: MemoryStore,
        retriever: Optional[DocumentRetriever],
    ):
        """Create RAG agent instance.

        Args:
            llm: LLM provider
            memory: Memory store
            retriever: Document retriever

        Returns:
            RAGAgent instance or None if retriever not available
        """
        if not retriever:
            return None
        from src.agents.rag_agent import RAGAgent

        return RAGAgent(
            llm=llm,
            retriever=retriever,
            memory=memory,
        )

    @staticmethod
    def create_web_search(
        llm: LLMProvider,
        memory: MemoryStore,
        tool_registry,
    ):
        """Create web search agent instance.

        Args:
            llm: LLM provider
            memory: Memory store
            tool_registry: Tool registry

        Returns:
            WebSearchAgent instance or None if search tool not available
        """
        search_tool = tool_registry.get("web_search") if tool_registry else None
        if not search_tool:
            return None
        from src.agents.web_search_agent import WebSearchAgent

        return WebSearchAgent(
            llm=llm,
            search_tool=search_tool,
            memory=memory,
        )
