"""Redis-based memory store for production."""

import json

import redis.asyncio as redis

from src.core.logging import get_logger
from src.memory.factory import MemoryStoreFactory
from src.utils.token_counter import truncate_messages

logger = get_logger(__name__)


@MemoryStoreFactory.register("redis")
class RedisStore:
    """Redis-based memory store with TTL support.

    Persistent across restarts with automatic expiration.
    """

    def __init__(self, url: str, ttl: int = 3600):
        self.url = url
        self.ttl = ttl
        self._client: redis.Redis | None = None
        self._summary_ttl = ttl * 2  # Summaries persist longer than messages

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(self.url, decode_responses=True)
            logger.info("redis_client_created", url=self.url)
        return self._client

    async def get_messages(self, session_id: str) -> list[dict]:
        """Get conversation history for a session."""
        client = await self._get_client()
        key = self._get_key(session_id)
        data = await client.lrange(key, 0, -1)
        return [json.loads(item) for item in data]

    async def add_message(self, session_id: str, message: dict) -> None:
        """Add a message to the session history."""
        client = await self._get_client()
        key = self._get_key(session_id)
        await client.rpush(key, json.dumps(message, ensure_ascii=False))
        await client.expire(key, self.ttl)
        logger.debug(
            "message_added",
            session_id=session_id,
            role=message.get("role"),
        )

    async def clear(self, session_id: str) -> None:
        """Clear session history."""
        client = await self._get_client()
        key = self._get_key(session_id)
        await client.delete(key)
        logger.debug("session_cleared", session_id=session_id)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("redis_client_closed")

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
        client = await self._get_client()
        key = self._get_summary_key(session_id)
        await client.set(key, summary, ex=self._summary_ttl)
        logger.debug(
            "summary_added",
            session_id=session_id,
            summary_length=len(summary),
            ttl=self._summary_ttl,
        )

    async def get_summary(self, session_id: str) -> str | None:
        """Get the conversation summary for a session.

        Args:
            session_id: Session identifier

        Returns:
            Summary text or None if no summary exists
        """
        client = await self._get_client()
        key = self._get_summary_key(session_id)
        summary = await client.get(key)
        if summary:
            logger.debug("summary_retrieved", session_id=session_id)
            return summary
        return None

    def _get_key(self, session_id: str) -> str:
        """Get Redis key for a session."""
        return f"chat:session:{session_id}"

    def _get_summary_key(self, session_id: str) -> str:
        """Get Redis key for a session summary."""
        return f"chat:summary:{session_id}"
