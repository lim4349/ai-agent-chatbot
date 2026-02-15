"""In-memory store for development and testing."""

from collections import defaultdict

from src.core.logging import get_logger
from src.memory.factory import MemoryStoreFactory
from src.utils.token_counter import truncate_messages

logger = get_logger(__name__)


@MemoryStoreFactory.register("in_memory")
class InMemoryStore:
    """Dictionary-based memory store for development/testing.

    Not persistent - data is lost on restart.
    """

    def __init__(self):
        self._store: dict[str, list[dict]] = defaultdict(list)
        self._summaries: dict[str, str] = {}
        logger.debug("in_memory_store_initialized")

    async def get_messages(self, session_id: str) -> list[dict]:
        """Get conversation history for a session."""
        return self._store[session_id].copy()

    async def add_message(self, session_id: str, message: dict) -> None:
        """Add a message to the session history."""
        self._store[session_id].append(message)
        logger.debug(
            "message_added",
            session_id=session_id,
            role=message.get("role"),
            message_length=len(message.get("content", "")),
        )

    async def clear(self, session_id: str) -> None:
        """Clear session history."""
        self._store.pop(session_id, None)
        self._summaries.pop(session_id, None)
        logger.debug("session_cleared", session_id=session_id)

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
        messages = await self.get_messages(session_id)
        return truncate_messages(messages, max_tokens=max_tokens)

    async def add_summary(self, session_id: str, summary: str) -> None:
        """Add or update a conversation summary.

        Args:
            session_id: Session identifier
            summary: Summary text to store
        """
        self._summaries[session_id] = summary
        logger.debug("summary_added", session_id=session_id, summary_length=len(summary))

    async def get_summary(self, session_id: str) -> str | None:
        """Get the conversation summary for a session.

        Args:
            session_id: Session identifier

        Returns:
            Summary text or None if no summary exists
        """
        summary = self._summaries.get(session_id)
        if summary:
            logger.debug("summary_retrieved", session_id=session_id)
        return summary

    def get_session_count(self) -> int:
        """Get the number of active sessions (for monitoring)."""
        return len(self._store)
