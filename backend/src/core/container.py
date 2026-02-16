"""Dependency Injection container."""

from dataclasses import dataclass, field
from functools import cached_property

from src.core.config import AppConfig
from src.core.protocols import (
    DocumentChunker,
    DocumentParser,
    DocumentRetriever,
    LLMProvider,
    MemoryStore,
    MemoryTool,
    Summarizer,
    TopicMemory,
    UserProfiler,
)
from src.memory.long_term_memory import LongTermMemory

# Lazy imports to avoid circular imports
_embedding_generator = None
_document_vector_store = None


def _get_embedding_generator():
    global _embedding_generator
    if _embedding_generator is None:
        from src.documents.embeddings import EmbeddingGenerator

        _embedding_generator = EmbeddingGenerator
    return _embedding_generator


def _get_document_vector_store():
    global _document_vector_store
    if _document_vector_store is None:
        from src.documents.store import DocumentVectorStore

        _document_vector_store = DocumentVectorStore
    return _document_vector_store


@dataclass
class Container:
    """Manual DI container.

    - Explicit dependency resolution (no framework magic)
    - Lazy initialization (created on actual use)
    - override() for test mock replacement
    """

    config: AppConfig

    # --- override slots (for testing) ---
    _llm_override: LLMProvider | None = field(default=None, repr=False)
    _memory_override: MemoryStore | None = field(default=None, repr=False)
    _retriever_override: DocumentRetriever | None = field(default=None, repr=False)
    _long_term_memory_override: LongTermMemory | None = field(default=None, repr=False)
    _summarizer_override: object | None = field(default=None, repr=False)
    _user_profiler_override: object | None = field(default=None, repr=False)
    _topic_memory_override: object | None = field(default=None, repr=False)
    _memory_tool_override: object | None = field(default=None, repr=False)
    _document_parser_override: DocumentParser | None = field(default=None, repr=False)
    _document_chunker_override: DocumentChunker | None = field(default=None, repr=False)

    # --- Provider accessors ---

    @cached_property
    def llm(self) -> LLMProvider:
        """Get LLM provider instance."""
        if self._llm_override:
            return self._llm_override
        from src.llm.factory import LLMFactory

        return LLMFactory.create(self.config.llm)

    @cached_property
    def memory(self) -> MemoryStore:
        """Get memory store instance."""
        if self._memory_override:
            return self._memory_override
        from src.memory.factory import MemoryStoreFactory

        return MemoryStoreFactory.create(self.config.memory)

    @cached_property
    def embedding_generator(self):
        """Get embedding generator instance based on provider configuration."""
        from src.documents.embeddings import create_embedding_generator

        provider = self.config.rag.embedding_provider
        model = self.config.rag.embedding_model

        # Determine API key based on provider
        if provider == "pinecone":
            api_key = self.config.rag.pinecone_api_key
        else:
            api_key = self.config.llm.openai_api_key

        return create_embedding_generator(
            provider=provider,
            model=model,
            api_key=api_key,
        )

    @cached_property
    def vector_store(self):
        """Get document vector store instance (Pinecone)."""
        from src.documents.pinecone_store import PineconeVectorStore

        return PineconeVectorStore(
            api_key=self.config.rag.pinecone_api_key,
            index_name=self.config.rag.pinecone_index_name,
            namespace=self.config.rag.pinecone_namespace,
            embedding_generator=self.embedding_generator,
        )

    @cached_property
    def retriever(self) -> DocumentRetriever | None:
        """Get document retriever instance (optional)."""
        if self._retriever_override:
            return self._retriever_override

        # Create Pinecone retriever with vector store and parser/chunker
        from src.documents.retriever_impl import PineconeDocumentRetriever

        return PineconeDocumentRetriever(
            vector_store=self.vector_store,
            parser=self.document_parser,
            chunker=self.document_chunker,
        )

    @cached_property
    def long_term_memory(self) -> LongTermMemory | None:
        """Get long-term memory instance."""
        if self._long_term_memory_override:
            return self._long_term_memory_override

        # Only enable in production or when explicitly configured
        if self.config.memory.backend == "in_memory" and not self.config.debug:
            return None

        # Configure based on environment
        persist_dir = None
        if self.config.memory.backend == "redis":
            # Use persistent storage for Redis-backed deployments
            persist_dir = "/data/chroma_db"

        return LongTermMemory(
            persist_directory=persist_dir,
            anonymize=not self.config.debug,  # Don't anonymize in debug mode
        )

    @cached_property
    def tool_registry(self):
        """Get tool registry with all configured tools."""
        from src.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Register web search tool if API key is configured
        if self.config.tools.tavily_api_key:
            from src.tools.web_search import WebSearchTool

            registry.register(WebSearchTool(self.config.tools.tavily_api_key))

        # Register retriever tool if available
        if self.retriever:
            from src.tools.retriever import RetrieverTool

            registry.register(RetrieverTool(self.retriever))

        # Register code executor if enabled
        if self.config.tools.code_execution_enabled:
            from src.tools.code_executor import CodeExecutorTool

            registry.register(CodeExecutorTool(self.config.tools.code_execution_timeout))

        return registry

    @cached_property
    def summarizer(self) -> Summarizer | None:
        """Summarization manager for auto-summarization."""
        if self._summarizer_override:
            return self._summarizer_override
        from src.core.auto_summarize import SummarizationManager
        from src.llm.factory import LLMFactory

        llm = LLMFactory.create(self.config.llm)
        return SummarizationManager(
            llm=llm,
            memory_store=self.memory,
        )

    @cached_property
    def user_profiler(self) -> UserProfiler | None:
        """User preference profiling."""
        if self._user_profiler_override:
            return self._user_profiler_override
        if self.long_term_memory:
            from src.core.user_profiler import UserProfiler
            from src.llm.factory import LLMFactory

            llm = LLMFactory.create(self.config.llm)
            return UserProfiler(llm=llm, long_term_memory=self.long_term_memory)
        return None

    @cached_property
    def topic_memory(self) -> TopicMemory | None:
        """Cross-session topic memory."""
        if self._topic_memory_override:
            return self._topic_memory_override
        if self.long_term_memory:
            from src.core.topic_memory import TopicMemory
            from src.llm.factory import LLMFactory

            llm = LLMFactory.create(self.config.llm)
            return TopicMemory(llm=llm, long_term_memory=self.long_term_memory)
        return None

    @cached_property
    def memory_tool(self) -> MemoryTool | None:
        """Semantic memory search tool."""
        if self._memory_tool_override:
            return self._memory_tool_override
        if self.memory and self.embedding_generator:
            from src.tools.memory_tool import MemoryTool

            return MemoryTool(
                memory_store=self.memory,
                embedding_provider=self.embedding_generator,
            )
        return None

    @cached_property
    def document_parser(self) -> DocumentParser:
        """Document parser instance."""
        if self._document_parser_override:
            return self._document_parser_override
        from src.documents.factory import DocumentProcessorFactory

        return DocumentProcessorFactory.create_parser()

    @cached_property
    def document_chunker(self) -> DocumentChunker:
        """Document chunker instance."""
        if self._document_chunker_override:
            return self._document_chunker_override
        from src.documents.factory import DocumentProcessorFactory

        return DocumentProcessorFactory.create_chunker(self.config)

    @cached_property
    def graph(self):
        """Get compiled LangGraph instance."""
        from src.graph.builder import build_graph

        return build_graph(self)

    # --- Test support ---

    def override(self, **kwargs) -> "Container":
        """Create a new container with overridden dependencies.

        Usage:
            test_container = container.override(llm_override=mock_llm)
        """
        new = Container(config=self.config)
        for key, value in kwargs.items():
            if hasattr(new, f"_{key}_override"):
                setattr(new, f"_{key}_override", value)
        return new
