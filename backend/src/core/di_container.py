"""Dependency Injector based DI Container."""

from dependency_injector import containers, providers

from src.core.config import get_config

# --- Factory Functions (defined before class to avoid NameError) ---

def _create_llm(config):
    """Create LLM provider."""
    from src.llm.factory import LLMFactory
    return LLMFactory.create(config)


def _create_memory(config):
    """Create memory store."""
    from src.memory.factory import MemoryStoreFactory
    return MemoryStoreFactory.create(config)


def _create_embedding_generator(config):
    """Create embedding generator."""
    from src.documents.embeddings import EmbeddingGenerator
    return EmbeddingGenerator(
        model=config.rag.embedding_model,
        api_key=config.llm.openai_api_key,
    )


def _create_vector_store(config, embedding_generator):
    """Create document vector store (Pinecone)."""
    from src.documents.pinecone_store import PineconeVectorStore

    return PineconeVectorStore(
        api_key=config.rag.pinecone_api_key,
        index_name=config.rag.pinecone_index_name,
        namespace=config.rag.pinecone_namespace,
        embedding_generator=embedding_generator,
    )


def _create_retriever(vector_store, config):
    """Create document retriever (Pinecone)."""
    from src.documents.factory import DocumentProcessorFactory
    from src.documents.retriever_impl import PineconeDocumentRetriever

    return PineconeDocumentRetriever(
        vector_store=vector_store,
        parser=DocumentProcessorFactory.create_parser(),
        chunker=DocumentProcessorFactory.create_chunker(config),
    )


def _create_long_term_memory(config):
    """Create long-term memory."""
    from src.memory.long_term_memory import LongTermMemory

    if config.memory.backend == "in_memory" and not config.debug:
        return None

    persist_dir = None
    if config.memory.backend == "redis":
        persist_dir = "/data/chroma_db"

    return LongTermMemory(
        persist_directory=persist_dir,
        anonymize=not config.debug,
    )


def _create_tool_registry(config, retriever):
    """Create tool registry."""
    from src.tools.code_executor import CodeExecutorTool
    from src.tools.registry import ToolRegistry
    from src.tools.retriever import RetrieverTool
    from src.tools.web_search import WebSearchTool

    registry = ToolRegistry()

    if config.tools.tavily_api_key:
        registry.register(WebSearchTool(config.tools.tavily_api_key))

    if retriever:
        registry.register(RetrieverTool(retriever))

    if config.tools.code_execution_enabled:
        registry.register(CodeExecutorTool(config.tools.code_execution_timeout))

    return registry


def _create_summarizer(config, llm, memory):
    """Create summarizer."""
    from src.core.auto_summarize import SummarizationManager
    return SummarizationManager(llm=llm, memory_store=memory)


def _create_user_profiler(config, long_term_memory):
    """Create user profiler."""
    from src.core.user_profiler import UserProfiler
    from src.llm.factory import LLMFactory

    if not long_term_memory:
        return None

    llm = LLMFactory.create(config.llm)
    return UserProfiler(llm=llm, long_term_memory=long_term_memory)


def _create_topic_memory(config, long_term_memory):
    """Create topic memory."""
    from src.core.topic_memory import TopicMemory
    from src.llm.factory import LLMFactory

    if not long_term_memory:
        return None

    llm = LLMFactory.create(config.llm)
    return TopicMemory(llm=llm, long_term_memory=long_term_memory)


def _create_memory_tool(memory, embedding_generator):
    """Create memory tool."""
    from src.tools.memory_tool import MemoryTool
    if not memory or not embedding_generator:
        return None
    return MemoryTool(
        memory_store=memory,
        embedding_provider=embedding_generator,
    )


def _create_document_parser():
    """Create document parser."""
    from src.documents.factory import DocumentProcessorFactory
    return DocumentProcessorFactory.create_parser()


def _create_document_chunker(config):
    """Create document chunker."""
    from src.documents.factory import DocumentProcessorFactory
    return DocumentProcessorFactory.create_chunker(config)


def _create_graph(container):
    """Create compiled LangGraph instance."""
    from src.graph.builder import build_graph
    return build_graph(container)


class DIContainer(containers.DeclarativeContainer):
    """Main dependency injection container."""

    # Configuration provider
    config = providers.Singleton(get_config)

    # LLM Provider
    llm = providers.Singleton(
        _create_llm,
        config=config.provided.llm,
    )

    # Memory Store
    memory = providers.Singleton(
        _create_memory,
        config=config.provided.memory,
    )

    # Embedding Generator
    embedding_generator = providers.Singleton(
        _create_embedding_generator,
        config=config,
    )

    # Vector Store
    vector_store = providers.Singleton(
        _create_vector_store,
        config=config,
        embedding_generator=embedding_generator,
    )

    # Document Retriever
    retriever = providers.Singleton(
        _create_retriever,
        vector_store=vector_store,
        config=config,
    )

    # Long-term Memory
    long_term_memory = providers.Singleton(
        _create_long_term_memory,
        config=config,
    )

    # Tool Registry
    tool_registry = providers.Singleton(
        _create_tool_registry,
        config=config,
        retriever=retriever,
    )

    # Summarizer
    summarizer = providers.Factory(
        _create_summarizer,
        config=config,
        llm=llm,
        memory=memory,
    )

    # User Profiler
    user_profiler = providers.Factory(
        _create_user_profiler,
        config=config,
        long_term_memory=long_term_memory,
    )

    # Topic Memory
    topic_memory = providers.Factory(
        _create_topic_memory,
        config=config,
        long_term_memory=long_term_memory,
    )

    # Memory Tool
    memory_tool = providers.Factory(
        _create_memory_tool,
        memory=memory,
        embedding_generator=embedding_generator,
    )

    # Document Parser
    document_parser = providers.Factory(_create_document_parser)

    # Document Chunker
    document_chunker = providers.Factory(
        _create_document_chunker,
        config=config,
    )

    # Graph - built lazily with container reference
    graph = providers.Singleton(
        lambda self: _create_graph(self),
        providers.Self(),
    )


# Global container instance
container = DIContainer()
