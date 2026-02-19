"""OpenAI LLM Provider."""

from collections.abc import AsyncIterator

from langchain_openai import ChatOpenAI

from src.core.config import LLMConfig
from src.core.di_container import container
from src.llm.factory import LLMFactory


@LLMFactory.register("openai")
class OpenAIProvider:
    """OpenAI API provider using langchain-openai."""

    def __init__(self, config: LLMConfig):
        self.config = config
        client_kwargs = {
            "model": config.model,
            "api_key": config.openai_api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        if config.base_url:
            client_kwargs["openai_api_base"] = config.base_url
        self.client = ChatOpenAI(**client_kwargs)
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
        """Generate structured output using function calling.

        Returns None if the LLM fails to generate structured output.
        """
        structured = self.client.with_structured_output(output_schema)
        result = await structured.ainvoke(messages, **kwargs)

        if result is None:
            return None

        if hasattr(result, "model_dump"):
            # Handle LangChain wrapper with 'parsed' field (suppresses Pydantic UserWarning)
            if hasattr(result, "parsed") and result.parsed is not None:
                inner = result.parsed
                return inner.model_dump() if hasattr(inner, "model_dump") else dict(inner)
            return result.model_dump()
        return result
