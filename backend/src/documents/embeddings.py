"""Embedding generator for document vectorization."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI, OpenAI


# Logger is initialized lazily to avoid circular imports
_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        from src.core.logging import get_logger
        _logger = get_logger(__name__)
    return _logger

# Default batch size for embedding requests
DEFAULT_BATCH_SIZE = 100
# Maximum retries for rate limiting
MAX_RETRIES = 3
# Delay between retries (seconds)
RETRY_DELAY = 1.0


class EmbeddingGenerator:
    """Generate embeddings using OpenAI's embedding models."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None):
        """Initialize the embedding generator.

        Args:
            model: OpenAI embedding model to use
            api_key: Optional OpenAI API key (uses env var if not provided)
        """
        self.model = model
        self._api_key = api_key
        self._async_client: AsyncOpenAI | None = None
        self._sync_client: OpenAI | None = None

    def _get_async_client(self) -> AsyncOpenAI:
        """Get or create async OpenAI client."""
        if self._async_client is None:
            from openai import AsyncOpenAI

            self._async_client = AsyncOpenAI(api_key=self._api_key)
        return self._async_client

    def _get_sync_client(self) -> OpenAI:
        """Get or create sync OpenAI client."""
        if self._sync_client is None:
            from openai import OpenAI

            self._sync_client = OpenAI(api_key=self._api_key)
        return self._sync_client

    async def generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts asynchronously.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter out empty strings
        valid_texts = [t if t.strip() else " " for t in texts]

        all_embeddings: list[list[float]] = []

        # Process in batches
        for i in range(0, len(valid_texts), DEFAULT_BATCH_SIZE):
            batch = valid_texts[i : i + DEFAULT_BATCH_SIZE]
            batch_embeddings = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _embed_batch_with_retry(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts with retry logic for rate limiting.

        Args:
            texts: Batch of texts to embed

        Returns:
            List of embedding vectors
        """
        client = self._get_async_client()
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.embeddings.create(
                    model=self.model,
                    input=texts,
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit errors
                if "rate limit" in error_str or "429" in error_str:
                    wait_time = RETRY_DELAY * (2**attempt)  # Exponential backoff
                    _get_logger().warning(
                        "embedding_rate_limit_hit",
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        wait_time=wait_time,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Non-retryable error
                    _get_logger().error("embedding_failed", error=str(e))
                    raise

        # All retries exhausted
        _get_logger().error(
            "embedding_max_retries_exceeded",
            error=str(last_error),
            batch_size=len(texts),
        )
        raise last_error or RuntimeError("Max retries exceeded for embedding generation")

    def generate_sync(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings synchronously.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter out empty strings
        valid_texts = [t if t.strip() else " " for t in texts]

        all_embeddings: list[list[float]] = []
        client = self._get_sync_client()

        # Process in batches
        for i in range(0, len(valid_texts), DEFAULT_BATCH_SIZE):
            batch = valid_texts[i : i + DEFAULT_BATCH_SIZE]

            for attempt in range(MAX_RETRIES):
                try:
                    response = client.embeddings.create(
                        model=self.model,
                        input=batch,
                    )
                    batch_embeddings = [item.embedding for item in response.data]
                    all_embeddings.extend(batch_embeddings)
                    break
                except Exception as e:
                    error_str = str(e).lower()

                    if "rate limit" in error_str or "429" in error_str:
                        wait_time = RETRY_DELAY * (2**attempt)
                        _get_logger().warning(
                            "embedding_rate_limit_hit_sync",
                            attempt=attempt + 1,
                            max_retries=MAX_RETRIES,
                            wait_time=wait_time,
                        )
                        import time

                        time.sleep(wait_time)
                    else:
                        _get_logger().error("embedding_sync_failed", error=str(e))
                        raise
            else:
                # All retries exhausted
                raise RuntimeError("Max retries exceeded for sync embedding generation")

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string.

        Args:
            query: Query text to embed

        Returns:
            Single embedding vector
        """
        embeddings = await self.generate([query])
        return embeddings[0] if embeddings else []
