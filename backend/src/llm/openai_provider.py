"""OpenAI LLM Provider."""

import warnings
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

        # Normalize content: some models (Anthropic/Gemini via OpenRouter) return a list of blocks
        content = response.content
        if isinstance(content, list):
            content = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        result = str(content).strip() if content else "죄송합니다. 응답을 생성하지 못했습니다."

        # Cache the response
        await self._cache.set(
            messages=messages,
            model=self.config.model,
            temperature=self.config.temperature,
            response=result,
        )

        return result

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

        return self._extract_structured_result(result)

    def _extract_structured_result(self, result) -> dict | None:
        """Extract structured result, handling LangChain wrapper objects.

        LangChain's with_structured_output may return a wrapper object with a
        'parsed' field containing the actual Pydantic model. This method safely
        extracts the inner value while suppressing serialization warnings.
        """
        # Suppress Pydantic serialization warnings when accessing wrapper attributes
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)

            if hasattr(result, "parsed") and result.parsed is not None:
                # LangChain wrapper - extract inner Pydantic model
                inner = result.parsed
                if hasattr(inner, "model_dump"):
                    return inner.model_dump()
                elif isinstance(inner, dict):
                    return inner
                else:
                    # Fallback: convert to dict manually
                    try:
                        return dict(inner)
                    except (TypeError, ValueError):
                        return {"result": str(inner)}

            if hasattr(result, "model_dump"):
                return result.model_dump()

            if isinstance(result, dict):
                return result

            # Last resort: try to access __dict__
            try:
                if hasattr(result, "__dict__"):
                    return result.__dict__
            except Exception:
                pass

        return None
