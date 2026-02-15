"""Factory for creating agent instances."""

from src.core.container import Container


class AgentFactory:
    """Factory for creating agent instances."""

    @staticmethod
    def create_supervisor(container: Container):
        """Create supervisor agent instance.

        Args:
            container: DI container

        Returns:
            SupervisorAgent instance
        """
        from src.agents.supervisor import SupervisorAgent

        available_agents = {"chat", "code"}
        if container.retriever:
            available_agents.add("rag")
        if container.tool_registry.get("web_search"):
            available_agents.add("web_search")

        return SupervisorAgent(
            llm=container.llm,
            available_agents=available_agents,
            memory=container.memory,
            memory_tool=container.memory_tool,
        )

    @staticmethod
    def create_chat(container: Container):
        """Create chat agent instance.

        Args:
            container: DI container

        Returns:
            ChatAgent instance
        """
        from src.agents.chat_agent import ChatAgent

        return ChatAgent(
            llm=container.llm,
            memory=container.memory,
            long_term_memory=container.long_term_memory,
            user_profiler=container.user_profiler,
            topic_memory=container.topic_memory,
            summarizer=container.summarizer,
        )

    @staticmethod
    def create_code(container: Container):
        """Create code agent instance.

        Args:
            container: DI container

        Returns:
            CodeAgent instance
        """
        from src.agents.code_agent import CodeAgent

        code_executor = container.tool_registry.get("code_executor")
        return CodeAgent(
            llm=container.llm,
            code_executor=code_executor,
            memory=container.memory,
        )

    @staticmethod
    def create_rag(container: Container):
        """Create RAG agent instance.

        Args:
            container: DI container

        Returns:
            RAGAgent instance or None if retriever not available
        """
        if not container.retriever:
            return None
        from src.agents.rag_agent import RAGAgent

        return RAGAgent(
            llm=container.llm,
            retriever=container.retriever,
            memory=container.memory,
        )

    @staticmethod
    def create_web_search(container: Container):
        """Create web search agent instance.

        Args:
            container: DI container

        Returns:
            WebSearchAgent instance or None if search tool not available
        """
        search_tool = container.tool_registry.get("web_search")
        if not search_tool:
            return None
        from src.agents.web_search_agent import WebSearchAgent

        return WebSearchAgent(
            llm=container.llm,
            search_tool=search_tool,
            memory=container.memory,
        )
