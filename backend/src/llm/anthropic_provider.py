"""Anthropic LLM Provider."""

import json
import warnings
from collections.abc import AsyncIterator

from langchain_anthropic import ChatAnthropic

from src.core.config import LLMConfig
from src.core.di_container import container
from src.core.logging import get_logger
from src.llm.factory import LLMFactory

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
        # Check cache first
        cached = await self._cache.get(
            messages=messages,
            model=self.config.model,
            temperature=self.config.temperature,
        )
        if cached is not None:
            return cached

        response = await self.client.ainvoke(messages, **kwargs)

        # Normalize content: Anthropic returns a list of content blocks
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
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )

            logger.info("structured_output_raw", content_preview=content[:500] if content else None)

            # Parse JSON from response
            result = self._parse_json_response(content)
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

    def _parse_json_response(self, content: str) -> dict | None:
        """Parse JSON from LLM response, handling various formats."""
        if not content:
            return None

        content = content.strip()

        # Try direct parse first
        try:
            result = json.loads(content)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        import re

        # Look for ```json ... ``` blocks
        code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if code_block_match:
            try:
                result = json.loads(code_block_match.group(1).strip())
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in the response
        object_match = re.search(r"\{[\s\S]*\}", content)
        if object_match:
            try:
                result = json.loads(object_match.group(0))
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        logger.warning("json_parse_failed", content_preview=content[:200])
        return None

    def _extract_structured_result(self, result) -> dict | None:
        """Extract structured result, handling LangChain wrapper objects."""
        # Suppress Pydantic serialization warnings when accessing wrapper attributes
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)

            if hasattr(result, "parsed") and result.parsed is not None:
                inner = result.parsed
                if hasattr(inner, "model_dump"):
                    return inner.model_dump()
                elif isinstance(inner, dict):
                    return inner
                else:
                    try:
                        return dict(inner)
                    except (TypeError, ValueError):
                        return {"result": str(inner)}

            if hasattr(result, "model_dump"):
                return result.model_dump()

            if isinstance(result, dict):
                return result

            try:
                if hasattr(result, "__dict__"):
                    return result.__dict__
            except Exception:
                pass

        return None
