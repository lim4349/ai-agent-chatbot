"""Anthropic LLM Provider."""

import json
from collections.abc import AsyncIterator

from langchain_anthropic import ChatAnthropic

from src.core.config import LLMConfig
from src.core.di_container import container
from src.core.logging import get_logger
from src.llm.factory import LLMFactory
from src.llm.invocation import (
    extract_structured_result,
    generate_with_cache,
    normalize_content,
    parse_json_response,
)

logger = get_logger(__name__)


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
        """Generate structured output using JSON mode.

        For z.ai and Anthropic-compatible APIs, uses JSON mode instead of
        function calling for structured output.

        Returns None if the LLM fails to generate structured output.
        """
        # Ensure the last message instructs JSON output
        enhanced_messages = self._ensure_json_instruction(messages, output_schema)

        try:
            # Use regular invoke - the prompt already requests JSON format
            response = await self.client.ainvoke(enhanced_messages, **kwargs)

            # Extract text content from response
            content = normalize_content(response.content)

            logger.info("structured_output_raw", content_preview=content[:500] if content else None)

            # Parse JSON from response
            result = parse_json_response(content)
            logger.debug("structured_output_parsed", result=result)

            return result

        except Exception as e:
            logger.error("structured_output_failed", error=str(e))
            return None

    def _ensure_json_instruction(
        self, messages: list[dict[str, str]], output_schema: type
    ) -> list[dict[str, str]]:
        """Ensure the last message instructs JSON output format."""
        # Create a copy of messages
        enhanced = list(messages)

        # Generate example from schema instead of sending raw schema
        example_hint = ""
        if output_schema is not dict and hasattr(output_schema, "model_json_schema"):
            try:
                schema = output_schema.model_json_schema()
                example = self._schema_to_example(schema)
                example_hint = f"\n\nRespond with valid JSON in this format:\n{json.dumps(example, indent=2, ensure_ascii=False)}"
            except Exception:
                pass

        # Check if last message already has JSON instruction
        last_msg = enhanced[-1] if enhanced else {}
        last_content = last_msg.get("content", "")

        if "json" not in last_content.lower():
            # Append JSON instruction to last message
            enhanced[-1] = {
                "role": last_msg.get("role", "user"),
                "content": f"{last_content}\n\nRespond with valid JSON only.{example_hint}",
            }

        return enhanced

    def _schema_to_example(self, schema: dict) -> dict:
        """Convert JSON schema to an example JSON object.

        Args:
            schema: JSON schema dict

        Returns:
            Example JSON object based on schema structure
        """
        example = {}
        properties = schema.get("properties", {})

        for key, prop in properties.items():
            prop_type = prop.get("type", "string")

            if prop_type == "string":
                # Use description as example if available
                desc = prop.get("description", "")
                if key == "selected_agent":
                    example[key] = "code"  # Common agent example
                elif key == "reasoning":
                    example[key] = "Brief explanation of the decision"
                else:
                    example[key] = desc or f"value for {key}"
            elif prop_type == "array":
                example[key] = []
            elif prop_type == "object":
                example[key] = {}
            elif prop_type == "boolean":
                example[key] = True
            elif prop_type == "number" or prop_type == "integer":
                example[key] = 0
            else:
                example[key] = None

        return example

    def _extract_structured_result(self, result) -> dict | None:
        """Backward-compatible wrapper around shared structured extraction."""
        return extract_structured_result(result)
