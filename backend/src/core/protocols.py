"""Protocol interfaces for dependency injection."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """LLM communication interface."""

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> str:
        """Generate a single response."""
        ...

    async def stream(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> AsyncIterator[str]:
        """Generate a streaming response."""
        ...

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        output_schema: type,
        **kwargs,
    ) -> dict:
        """Generate structured output using function calling or JSON mode."""
        ...


@runtime_checkable
class MemoryStore(Protocol):
    """Conversation memory interface."""

    async def get_messages(self, session_id: str) -> list[dict]:
        """Get conversation history for a session."""
        ...

    async def add_message(self, session_id: str, message: dict) -> None:
        """Add a message to the session history."""
        ...

    async def clear(self, session_id: str) -> None:
        """Clear session history."""
        ...

    async def get_messages_with_limit(
        self,
        session_id: str,
        max_tokens: int,
    ) -> list[dict]:
        """Get conversation history limited by token count.

        Args:
            session_id: Session identifier
            max_tokens: Maximum tokens to return

        Returns:
            List of messages that fit within token limit
        """
        ...

    async def add_summary(self, session_id: str, summary: str) -> None:
        """Add or update a conversation summary.

        Args:
            session_id: Session identifier
            summary: Summary text to store
        """
        ...

    async def get_summary(self, session_id: str) -> str | None:
        """Get the conversation summary for a session.

        Args:
            session_id: Session identifier

        Returns:
            Summary text or None if no summary exists
        """
        ...


@runtime_checkable
class DocumentRetriever(Protocol):
    """Document retrieval interface for RAG."""

    async def retrieve(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict]:
        """Retrieve relevant document chunks.

        Returns: [{"content": str, "metadata": dict, "score": float}]
        """
        ...

    async def add_documents(self, documents: list[dict]) -> None:
        """Add documents (embed + store)."""
        ...


@runtime_checkable
class Tool(Protocol):
    """Tool interface for agent use."""

    @property
    def name(self) -> str:
        """Tool name."""
        ...

    @property
    def description(self) -> str:
        """Tool description."""
        ...

    async def execute(self, **kwargs) -> str:
        """Execute the tool with given arguments."""
        ...


@runtime_checkable
class DocumentParser(Protocol):
    """Document parser interface for parsing various file formats."""

    def parse_from_bytes(
        self,
        content: bytes,
        file_type: str,
    ) -> list:
        """Parse document from bytes.

        Args:
            content: Raw file bytes
            file_type: Type of file (pdf, docx, txt, md, csv, json)

        Returns:
            List of DocumentSection objects

        """
        ...

    def parse(
        self,
        file_path: str,
        file_type: str,
    ) -> list:
        """Parse document from file path.

        Args:
            file_path: Path to the file to parse
            file_type: Type of file (pdf, docx, txt, md, csv, json)

        Returns:
            List of DocumentSection objects

        """
        ...


@runtime_checkable
class DocumentChunker(Protocol):
    """Document chunker interface for splitting documents into chunks."""

    def chunk(
        self,
        sections: list,
        source: str = "",
    ) -> list:
        """Chunk document sections respecting structure.

        Args:
            sections: List of document sections to chunk
            source: Source identifier for the document

        Returns:
            List of Chunk objects

        """
        ...


@runtime_checkable
class Summarizer(Protocol):
    """Summarization interface for conversation summarization."""

    async def summarize(self, session_id: str, messages: list[dict]) -> str | None:
        """Generate summary for conversation messages.

        Args:
            session_id: Session identifier
            messages: List of conversation messages

        Returns:
            Summary text or None if not triggered
        """
        ...


@runtime_checkable
class UserProfiler(Protocol):
    """User profiling interface for extracting user preferences."""

    async def extract_profile(self, session_id: str, messages: list[dict]) -> dict | None:
        """Extract user profile from conversation.

        Args:
            session_id: Session identifier
            messages: List of conversation messages

        Returns:
            User profile data or None
        """
        ...

    async def get_profile(self, user_id: str) -> dict | None:
        """Get stored user profile.

        Args:
            user_id: User identifier

        Returns:
            User profile data or None
        """
        ...


@runtime_checkable
class TopicMemory(Protocol):
    """Topic memory interface for cross-session topic tracking."""

    async def extract_topics(self, session_id: str, messages: list[dict]) -> list[str]:
        """Extract topics from conversation.

        Args:
            session_id: Session identifier
            messages: List of conversation messages

        Returns:
            List of topic strings
        """
        ...

    async def get_related_sessions(self, topic: str) -> list[str]:
        """Get sessions related to a topic.

        Args:
            topic: Topic to search for

        Returns:
            List of session IDs
        """
        ...


@runtime_checkable
class MemoryTool(Protocol):
    """Memory tool interface for semantic memory search."""

    @property
    def name(self) -> str:
        """Tool name."""
        ...

    @property
    def description(self) -> str:
        """Tool description."""
        ...

    async def execute(self, query: str, **kwargs) -> str:
        """Execute memory search.

        Args:
            query: Search query
            **kwargs: Additional arguments

        Returns:
            Search results as formatted string
        """
        ...
