"""Redis-based LLM response caching."""

import hashlib
import json

import redis.asyncio as redis

from src.core.logging import get_logger

logger = get_logger(__name__)


class LLMCache:
    """Redis-based cache for LLM responses.

    Cache key is computed from: messages hash + model + temperature
    """

    def __init__(
        self,
        redis_url: str,
        ttl_seconds: int = 3600,
        enabled: bool = True,
    ):
        """Initialize LLM cache.

        Args:
            redis_url: Redis connection URL
            ttl_seconds: Time-to-live for cached responses (default 1 hour)
            enabled: Whether caching is enabled
        """
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled
        self._client: redis.Redis | None = None
        self._key_prefix = "llm:cache:"

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            logger.info("llm_cache_redis_client_created", url=self.redis_url)
        return self._client

    def _make_key(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
    ) -> str:
        """Generate cache key from request parameters.

        Args:
            messages: Conversation messages
            model: Model name
            temperature: Temperature parameter

        Returns:
            Redis key string
        """
        key_data = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
        }
        key_hash = hashlib.sha256(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()
        return f"{self._key_prefix}{key_hash}"

    async def get(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
    ) -> str | None:
        """Get cached response if available.

        Args:
            messages: Conversation messages
            model: Model name
            temperature: Temperature parameter

        Returns:
            Cached response text or None if not found
        """
        if not self.enabled:
            return None

        try:
            client = await self._get_client()
            key = self._make_key(messages, model, temperature)
            cached = await client.get(key)
            if cached:
                logger.debug("llm_cache_hit", model=model, key=key[:16])
                return cached
            logger.debug("llm_cache_miss", model=model, key=key[:16])
            return None
        except Exception as e:
            logger.warning("llm_cache_get_failed", error=str(e))
            return None

    async def set(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        response: str,
    ) -> None:
        """Cache a response.

        Args:
            messages: Conversation messages
            model: Model name
            temperature: Temperature parameter
            response: Response text to cache
        """
        if not self.enabled:
            return

        try:
            client = await self._get_client()
            key = self._make_key(messages, model, temperature)
            await client.set(key, response, ex=self.ttl_seconds)
            logger.debug(
                "llm_cache_set",
                model=model,
                key=key[:16],
                ttl=self.ttl_seconds,
                response_length=len(response),
            )
        except Exception as e:
            logger.warning("llm_cache_set_failed", error=str(e))

    async def clear(self) -> None:
        """Clear all cached LLM responses."""
        try:
            client = await self._get_client()
            pattern = f"{self._key_prefix}*"
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await client.delete(*keys)
                logger.info("llm_cache_cleared", count=len(keys))
        except Exception as e:
            logger.warning("llm_cache_clear_failed", error=str(e))

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("llm_cache_redis_client_closed")
