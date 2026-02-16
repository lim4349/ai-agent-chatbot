"""Embedding generator for document vectorization.

Supports multiple providers:
- OpenAI (default, requires OPENAI_API_KEY)
- Pinecone Inference (free, requires PINECONE_API_KEY)
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

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


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    async def generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        ...


class BaseEmbeddingGenerator(ABC):
    """Base class for embedding generators."""

    @abstractmethod
    async def generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        embeddings = await self.generate([query])
        return embeddings[0] if embeddings else []


class EmbeddingGenerator(BaseEmbeddingGenerator):
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


class PineconeInferenceEmbedding(BaseEmbeddingGenerator):
    """Generate embeddings using Pinecone Inference API (free).

    Uses Pinecone's hosted embedding models without requiring OpenAI API key.
    Supported models: multilingual-e5-large, llama-text-embed-v2
    """

    def __init__(
        self,
        api_key: str,
        model: str = "multilingual-e5-large",
    ):
        """Initialize Pinecone Inference embedding generator.

        Args:
            api_key: Pinecone API key
            model: Embedding model to use (default: multilingual-e5-large)
        """
        self._api_key = api_key
        self.model = model
        self._pinecone_client = None

    def _get_client(self):
        """Get or create Pinecone client."""
        if self._pinecone_client is None:
            from pinecone import Pinecone
            self._pinecone_client = Pinecone(api_key=self._api_key)
        return self._pinecone_client

    async def generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts using Pinecone Inference.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter out empty strings
        valid_texts = [t if t.strip() else " " for t in texts]

        client = self._get_client()
        all_embeddings: list[list[float]] = []

        # Process in batches (Pinecone recommends max 96 items per request)
        batch_size = 96
        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i : i + batch_size]

            for attempt in range(MAX_RETRIES):
                try:
                    # Use asyncio.to_thread to avoid blocking event loop
                    response = await asyncio.to_thread(
                        client.inference.embed,
                        model=self.model,
                        inputs=batch,
                        parameters={"input_type": "passage", "truncate": "END"}
                    )

                    # Extract embeddings from response
                    batch_embeddings = [item.values for item in response.data]
                    all_embeddings.extend(batch_embeddings)
                    break

                except Exception as e:
                    error_str = str(e).lower()

                    if "rate limit" in error_str or "429" in error_str or "timeout" in error_str:
                        wait_time = RETRY_DELAY * (2 ** attempt)
                        _get_logger().warning(
                            "pinecone_embedding_retry",
                            attempt=attempt + 1,
                            max_retries=MAX_RETRIES,
                            wait_time=wait_time,
                            error=str(e),
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        _get_logger().error("pinecone_embedding_failed", error=str(e))
                        raise
            else:
                raise RuntimeError(f"Max retries exceeded for Pinecone embedding, batch starting at {i}")

        _get_logger().info(
            "pinecone_embeddings_generated",
            model=self.model,
            count=len(all_embeddings),
        )

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string for search.

        Uses 'query' input_type for better search performance.

        Args:
            query: Query text to embed

        Returns:
            Single embedding vector
        """
        if not query.strip():
            return []

        client = self._get_client()

        for attempt in range(MAX_RETRIES):
            try:
                # Use asyncio.to_thread to avoid blocking event loop
                response = await asyncio.to_thread(
                    client.inference.embed,
                    model=self.model,
                    inputs=[query],
                    parameters={"input_type": "query", "truncate": "END"}
                )
                return response.data[0].values if response.data else []

            except Exception as e:
                error_str = str(e).lower()

                if "rate limit" in error_str or "429" in error_str or "timeout" in error_str:
                    wait_time = RETRY_DELAY * (2 ** attempt)
                    _get_logger().warning(
                        "pinecone_query_embedding_retry",
                        attempt=attempt + 1,
                        error=str(e),
                    )
                    await asyncio.sleep(wait_time)
                else:
                    _get_logger().error("pinecone_query_embedding_failed", error=str(e))
                    raise
        raise RuntimeError("Max retries exceeded for Pinecone query embedding")


def create_embedding_generator(
    provider: str = "openai",
    model: str = "text-embedding-3-small",
    api_key: str | None = None,
) -> BaseEmbeddingGenerator:
    """Factory function to create embedding generator based on provider.

    Args:
        provider: Embedding provider ('openai' or 'pinecone')
        model: Model name to use
        api_key: API key for the provider

    Returns:
        Embedding generator instance
    """
    if provider == "pinecone":
        if not api_key:
            raise ValueError("Pinecone API key is required for Pinecone embedding provider")
        # Default to multilingual-e5-large for Pinecone
        if model == "text-embedding-3-small":
            model = "multilingual-e5-large"
        return PineconeInferenceEmbedding(api_key=api_key, model=model)
    else:
        # Default to OpenAI
        return EmbeddingGenerator(model=model, api_key=api_key)
