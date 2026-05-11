"""OpenAI LLM Provider."""

import warnings
from collections.abc import AsyncIterator

import httpx
from langchain_openai import ChatOpenAI

from src.core.config import LLMConfig
from src.core.di_container import container
from src.core.logging import get_logger
from src.llm.factory import LLMFactory
from src.llm.invocation import extract_structured_result, generate_with_cache, normalize_content

logger = get_logger(__name__)

# Suppress Pydantic serialization warnings emitted by LangChain's
# with_structured_output() wrapper. The warning fires inside async callbacks
# where context-manager-based suppression is unreliable.
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings",
    category=UserWarning,
)


@LLMFactory.register("lmstudio")
@LLMFactory.register("openai")
class OpenAIProvider:
    """OpenAI API provider using LangChain."""

    def __init__(self, config: LLMConfig):
        self.config = config
        base_url = config.base_url
        api_key = config.openai_api_key

        if config.provider == "lmstudio":
            base_url = base_url or "http://127.0.0.1:1234/v1"
            api_key = api_key or "lm-studio"
        elif base_url and not api_key:
            api_key = "local-api-key"

        # Configure httpx clients for Render Free Tier memory efficiency.
        # Both sync and async clients must be set — langchain-openai uses
        # http_client for sync calls and http_async_client for async calls.
        limits = httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
        )
        timeout = httpx.Timeout(30.0, connect=5.0)

        # LangChain client
        client_kwargs = {
            "model": config.model,
            "api_key": api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "http_client": httpx.Client(limits=limits, timeout=timeout),
            "http_async_client": httpx.AsyncClient(limits=limits, timeout=timeout),
        }
        if base_url:
            client_kwargs["base_url"] = base_url

        # Keep OpenRouter on free routes only. Model routing is handled by
        # openrouter/free when that model is configured.
        if base_url and "openrouter" in base_url:
            extra_body: dict = {
                "max_price": {"input": 0, "output": 0},
            }
            client_kwargs["extra_body"] = extra_body

        self.client = ChatOpenAI(**client_kwargs)
        self._cache = container.llm_cache()

    async def generate(self, messages: list[dict[str, str]], **kwargs) -> str:
        """Generate a single response."""
        content, _ = await self.generate_with_usage(messages, **kwargs)
        return content

    async def generate_with_usage(
        self, messages: list[dict[str, str]], **kwargs
    ) -> tuple[str, dict[str, int]]:
        """Generate a response with token usage info.

        Returns:
            Tuple of (content, {"input_tokens": int, "output_tokens": int})
        """
        return await generate_with_cache(
            cache=self._cache,
            client=self.client,
            config=self.config,
            messages=messages,
            **kwargs,
        )

    async def stream(self, messages: list[dict[str, str]], **kwargs) -> AsyncIterator[str]:
        """Generate a streaming response."""
        async for chunk in self.client.astream(messages, **kwargs):
            if chunk.content:
                yield normalize_content(chunk.content, strip=False)

    async def generate_structured(
        self, messages: list[dict[str, str]], output_schema: type, **kwargs
    ) -> dict | None:
        """Generate structured output using function calling.

        Returns None if the LLM fails to generate structured output.
        """
        structured = self.client.with_structured_output(output_schema)

        # Suppress Pydantic warnings during structured output generation
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=UserWarning,
                message=".*PydanticSerializationUnexpectedValue.*",
            )
            result = await structured.ainvoke(messages, **kwargs)

        if result is None:
            return None

        return extract_structured_result(result)
