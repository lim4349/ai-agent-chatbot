"""Redis-based memory store for production."""

import json
from collections.abc import Awaitable, Callable

import redis.asyncio as redis

from src.core.logging import get_logger
from src.memory.factory import MemoryStoreFactory
from src.memory.in_memory_store import InMemoryStore
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
        self._fallback = InMemoryStore()
        self._fallback_enabled = False

    def _masked_url(self) -> str:
        """Mask Redis credentials before logging."""
        if "@" not in self.url:
            return self.url
        prefix, suffix = self.url.split("@", 1)
        if ":" not in prefix:
            return f"[REDACTED]@{suffix}"
        scheme, _secret = prefix.rsplit(":", 1)
        return f"{scheme}:[REDACTED]@{suffix}"

    def _enable_fallback(self, error: Exception) -> None:
        """Switch to in-memory fallback after Redis failures."""
        if self._fallback_enabled:
            return
        self._fallback_enabled = True
        logger.warning(
            "redis_unavailable_falling_back_to_in_memory",
            error=str(error),
        )

    async def _get_client(self) -> redis.Redis | None:
        """Get or create Redis client."""
        if self._fallback_enabled:
            return None

        if self._client is None:
            try:
                url = self.url
                if "upstash.io" in url and url.startswith("redis://"):
                    url = "rediss://" + url[8:]
                self._client = redis.from_url(url, decode_responses=True)
                await self._client.ping()
                logger.info("redis_client_created", url=self._masked_url())
            except Exception as e:
                self._enable_fallback(e)
                self._client = None
                return None
        return self._client

    async def _with_fallback(
        self,
        redis_operation: Callable[[redis.Redis], Awaitable],
        fallback_operation: Callable[[], Awaitable],
    ):
        """Run Redis operation or transparently fall back to in-memory storage."""
        client = await self._get_client()
        if client is None:
            return await fallback_operation()

        try:
            return await redis_operation(client)
        except Exception as e:
            self._enable_fallback(e)
            return await fallback_operation()

    async def get_messages(self, session_id: str) -> list[dict]:
        """Get conversation history for a session."""
        key = self._get_key(session_id)
        return await self._with_fallback(
            lambda client: self._get_messages_from_redis(client, key),
            lambda: self._fallback.get_messages(session_id),
        )

    async def add_message(self, session_id: str, message: dict) -> None:
        """Add a message to the session history."""
        key = self._get_key(session_id)
        await self._with_fallback(
            lambda client: self._add_message_to_redis(client, key, session_id, message),
            lambda: self._fallback.add_message(session_id, message),
        )

    async def clear(self, session_id: str) -> None:
        """Clear session history."""
        key = self._get_key(session_id)
        await self._with_fallback(
            lambda client: self._clear_redis_key(client, key, session_id),
            lambda: self._fallback.clear(session_id),
        )

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
        key = self._get_summary_key(session_id)
        await self._with_fallback(
            lambda client: self._add_summary_to_redis(client, key, session_id, summary),
            lambda: self._fallback.add_summary(session_id, summary),
        )

    async def get_summary(self, session_id: str) -> str | None:
        """Get the conversation summary for a session.

        Args:
            session_id: Session identifier

        Returns:
            Summary text or None if no summary exists
        """
        key = self._get_summary_key(session_id)
        return await self._with_fallback(
            lambda client: self._get_summary_from_redis(client, key, session_id),
            lambda: self._fallback.get_summary(session_id),
        )

    async def _get_messages_from_redis(self, client: redis.Redis, key: str) -> list[dict]:
        data = await client.lrange(key, 0, -1)
        return [json.loads(item) for item in data]

    async def _add_message_to_redis(
        self,
        client: redis.Redis,
        key: str,
        session_id: str,
        message: dict,
    ) -> None:
        await client.rpush(key, json.dumps(message, ensure_ascii=False))
        await client.expire(key, self.ttl)
        logger.debug("message_added", session_id=session_id, role=message.get("role"))

    async def _clear_redis_key(self, client: redis.Redis, key: str, session_id: str) -> None:
        await client.delete(key)
        logger.debug("session_cleared", session_id=session_id)

    async def _add_summary_to_redis(
        self,
        client: redis.Redis,
        key: str,
        session_id: str,
        summary: str,
    ) -> None:
        await client.set(key, summary, ex=self._summary_ttl)
        logger.debug(
            "summary_added",
            session_id=session_id,
            summary_length=len(summary),
            ttl=self._summary_ttl,
        )

    async def _get_summary_from_redis(
        self,
        client: redis.Redis,
        key: str,
        session_id: str,
    ) -> str | None:
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
