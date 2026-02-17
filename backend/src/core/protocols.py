"""Protocol interfaces for dependency injection."""

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """LLM communication interface."""

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Generate a single response."""
        ...

    async def stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Generate a streaming response."""
        ...

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        output_schema: type,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Generate structured output using function calling or JSON mode.

        Returns None if the LLM fails to generate valid structured output.
        """
        ...


@runtime_checkable
class MemoryStore(Protocol):
    """Conversation memory interface."""

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get conversation history for a session."""
        ...

    async def add_message(self, session_id: str, message: dict[str, Any]) -> None:
        """Add a message to the session history."""
        ...

    async def clear(self, session_id: str) -> None:
        """Clear session history."""
        ...

    async def get_messages_with_limit(
        self,
        session_id: str,
        max_tokens: int,
    ) -> list[dict[str, Any]]:
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
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant document chunks.

        Args:
            query: Search query text
            top_k: Number of results to return
            session_id: Optional session ID for filtering documents

        Returns: [{"content": str, "metadata": dict, "score": float}]
        """
        ...

    async def add_documents(self, documents: list[dict[str, Any]]) -> None:
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

    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool with given arguments."""
        ...


@runtime_checkable
class DocumentParser(Protocol):
    """Document parser interface for parsing various file formats."""

    def parse_from_bytes(
        self,
        content: bytes,
        file_type: str,
    ) -> list[Any]:
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
    ) -> list[Any]:
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
        sections: list[Any],
        source: str = "",
    ) -> list[Any]:
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

    async def summarize(self, session_id: str, messages: list[dict[str, Any]]) -> str | None:
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

    async def extract_profile(
        self, session_id: str, messages: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Extract user profile from conversation.

        Args:
            session_id: Session identifier
            messages: List of conversation messages

        Returns:
            User profile data or None
        """
        ...

    async def get_profile(self, user_id: str) -> dict[str, Any] | None:
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

    async def extract_topics(self, session_id: str, messages: list[dict[str, Any]]) -> list[str]:
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

    async def execute(self, query: str, **kwargs: Any) -> str:
        """Execute memory search.

        Args:
            query: Search query
            **kwargs: Additional arguments

        Returns:
            Search results as formatted string
        """
        ...


@runtime_checkable
class SessionStore(Protocol):
    """Session storage interface."""

    async def create(
        self,
        session_id: str,
        user_id: str,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> object:
        """Create a new session.

        Args:
            session_id: Unique session identifier
            user_id: Owner user ID
            title: Session title
            metadata: Optional session metadata

        Returns:
            Created session object
        """
        ...

    async def get(self, session_id: str) -> object | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session object or None if not found
        """
        ...

    async def list_by_user(self, user_id: str) -> list[Any]:
        """List all sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of session objects
        """
        ...

    async def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        ...

    async def exists(self, session_id: str) -> bool:
        """Check if a session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists
        """
        ...
