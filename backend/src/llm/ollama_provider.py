"""Ollama LLM Provider for local models."""

import json
from collections.abc import AsyncIterator

from langchain_ollama import ChatOllama

from src.core.config import LLMConfig
from src.core.logging import get_logger
from src.llm.factory import LLMFactory

logger = get_logger(__name__)


@LLMFactory.register("ollama")
class OllamaProvider:
    """Ollama local LLM provider using langchain-ollama."""

    def __init__(self, config: LLMConfig):
        self.config = config
        base_url = config.base_url or "http://localhost:11434"
        self.client = ChatOllama(
            model=config.model,
            base_url=base_url,
            temperature=config.temperature,
            num_predict=config.max_tokens,
        )
        logger.info("ollama_provider_initialized", model=config.model, base_url=base_url)

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
        """Generate structured output.

        Ollama may not support structured output for all models,
        so we use JSON mode with explicit schema instructions as fallback.
        """
        try:
            # Try native structured output first
            structured = self.client.with_structured_output(output_schema)
            result = await structured.ainvoke(messages, **kwargs)
            if hasattr(result, "model_dump"):
                return result.model_dump()
            return result
        except Exception as e:
            logger.warning("ollama_structured_output_fallback", error=str(e))
            # Fallback: use JSON mode with explicit instructions
            schema = (
                output_schema.model_json_schema()
                if hasattr(output_schema, "model_json_schema")
                else {}
            )
            json_prompt = f"""You must respond with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

Respond ONLY with the JSON object, no additional text."""

            enhanced_messages = [{"role": "system", "content": json_prompt}, *messages]
            raw_response = await self.generate(enhanced_messages, **kwargs)

            # Parse JSON from response
            try:
                # Try to extract JSON from the response
                json_str = raw_response.strip()
                if json_str.startswith("```"):
                    # Remove code blocks if present
                    lines = json_str.split("\n")
                    json_str = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

                parsed = json.loads(json_str)
                return output_schema(**parsed).model_dump()
            except json.JSONDecodeError as parse_error:
                logger.error("ollama_json_parse_failed", error=str(parse_error))
                raise ValueError(
                    f"Failed to parse structured output: {parse_error}"
                ) from parse_error
