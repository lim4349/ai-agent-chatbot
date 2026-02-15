"""OpenAI LLM Provider."""

from collections.abc import AsyncIterator

from langchain_openai import ChatOpenAI

from src.core.config import LLMConfig
from src.llm.factory import LLMFactory


@LLMFactory.register("openai")
class OpenAIProvider:
    """OpenAI API provider using langchain-openai."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = ChatOpenAI(
            model=config.model,
            api_key=config.openai_api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    async def generate(self, messages: list[dict[str, str]], **kwargs) -> str:
        """Generate a single response."""
        response = await self.client.ainvoke(messages, **kwargs)
        return response.content

    async def stream(self, messages: list[dict[str, str]], **kwargs) -> AsyncIterator[str]:
        """Generate a streaming response."""
        async for chunk in self.client.astream(messages, **kwargs):
            if chunk.content:
                yield chunk.content

    async def generate_structured(
        self, messages: list[dict[str, str]], output_schema: type, **kwargs
    ) -> dict:
        """Generate structured output using function calling."""
        structured = self.client.with_structured_output(output_schema)
        result = await structured.ainvoke(messages, **kwargs)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result
