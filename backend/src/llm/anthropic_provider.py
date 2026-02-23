"""Anthropic LLM Provider."""

import warnings
from collections.abc import AsyncIterator

from langchain_anthropic import ChatAnthropic

from src.core.config import LLMConfig
from src.core.di_container import container
from src.llm.factory import LLMFactory


@LLMFactory.register("anthropic")
class AnthropicProvider:
    """Anthropic API provider using langchain-anthropic.

    Supports custom base_url for Anthropic-compatible APIs like GLM.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        client_kwargs = {
            "model": config.model,
            "api_key": config.anthropic_api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        # Support custom base URL for Anthropic-compatible APIs (e.g., GLM)
        if config.base_url:
            client_kwargs["anthropic_api_url"] = config.base_url
        self.client = ChatAnthropic(**client_kwargs)
        self._cache = container.llm_cache()

    async def generate(self, messages: list[dict[str, str]], **kwargs) -> str:
        """Generate a single response."""
        # Check cache first
        cached = await self._cache.get(
            messages=messages,
            model=self.config.model,
            temperature=self.config.temperature,
        )
        if cached is not None:
            return cached

        response = await self.client.ainvoke(messages, **kwargs)

        # Cache the response
        await self._cache.set(
            messages=messages,
            model=self.config.model,
            temperature=self.config.temperature,
            response=response.content,
        )

        return response.content

    async def stream(self, messages: list[dict[str, str]], **kwargs) -> AsyncIterator[str]:
        """Generate a streaming response."""
        async for chunk in self.client.astream(messages, **kwargs):
            if chunk.content:
                yield chunk.content

    async def generate_structured(
        self, messages: list[dict[str, str]], output_schema: type, **kwargs
    ) -> dict | None:
        """Generate structured output using tool use.

        Returns None if the LLM fails to generate structured output.
        """
        structured = self.client.with_structured_output(output_schema)
        result = await structured.ainvoke(messages, **kwargs)

        if result is None:
            return None

        # Suppress Pydantic serialization warnings for LangChain wrapper objects
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=UserWarning,
                message=".*PydanticSerializationUnexpectedValue.*",
            )
            return self._extract_structured_result(result)

    def _extract_structured_result(self, result) -> dict | None:
        """Extract structured result, handling LangChain wrapper objects."""
        if hasattr(result, "parsed") and result.parsed is not None:
            inner = result.parsed
            if hasattr(inner, "model_dump"):
                return inner.model_dump()
            elif isinstance(inner, dict):
                return inner
            else:
                return dict(inner)

        if hasattr(result, "model_dump"):
            return result.model_dump()

        if isinstance(result, dict):
            return result

        return None
