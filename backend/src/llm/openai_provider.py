"""OpenAI LLM Provider."""

import warnings
from collections.abc import AsyncIterator

import httpx
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from src.core.config import LLMConfig
from src.core.di_container import container
from src.core.logging import get_logger
from src.llm.factory import LLMFactory

logger = get_logger(__name__)

# Suppress Pydantic serialization warnings emitted by LangChain's
# with_structured_output() wrapper. The warning fires inside async callbacks
# where context-manager-based suppression is unreliable.
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings",
    category=UserWarning,
)


@LLMFactory.register("openai")
class OpenAIProvider:
    """OpenAI API provider using direct OpenAI SDK for rate limit capture."""

    def __init__(self, config: LLMConfig):
        self.config = config

        # Configure httpx client with memory-efficient limits for Render Free Tier
        limits = httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
        )
        http_client = httpx.Client(
            limits=limits,
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

        # LangChain client for structured output (kept for compatibility)
        client_kwargs = {
            "model": config.model,
            "api_key": config.openai_api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "http_client": http_client,
        }
        if config.base_url:
            client_kwargs["openai_api_base"] = config.base_url
        self.client = ChatOpenAI(**client_kwargs)
        self._cache = container.llm_cache()

        # Direct OpenAI SDK client for rate limit header capture
        self._openai_client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.base_url,
            timeout=30.0,
            max_retries=2,
        )
        self.last_rate_limit_info: dict = {}

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
        # Check cache first
        cached = await self._cache.get(
            messages=messages,
            model=self.config.model,
            temperature=self.config.temperature,
        )
        if cached is not None:
            return cached, {"input_tokens": 0, "output_tokens": 0}

        # Use direct OpenAI SDK with_raw_response to capture rate limit headers
        try:
            raw_response = await self._openai_client.chat.completions.with_raw_response.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                **kwargs,
            )

            # Parse the completion
            response = raw_response.parse()

            # Capture rate limit headers - log all headers for debugging
            headers = raw_response.headers
            logger.info("openai_response_headers", headers=dict(headers))

            # Try multiple header formats (OpenRouter may use different names)
            self.last_rate_limit_info = {
                "remaining_requests": self._safe_int(
                    headers.get("x-ratelimit-remaining-requests")
                    or headers.get("x-ratelimit-remaining")
                ),
                "remaining_tokens": self._safe_int(
                    headers.get("x-ratelimit-remaining-tokens")
                ),
                "limit_requests": self._safe_int(
                    headers.get("x-ratelimit-limit-requests")
                    or headers.get("x-ratelimit-limit")
                ),
                "limit_tokens": self._safe_int(
                    headers.get("x-ratelimit-limit-tokens")
                ),
            }

            # Extract content
            content = response.choices[0].message.content if response.choices else ""
            result = str(content).strip() if content else "죄송합니다. 응답을 생성하지 못했습니다."

            # Extract token usage
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

        except Exception as e:
            # Fallback to LangChain if direct SDK fails
            import logging
            logging.getLogger(__name__).warning(f"Direct OpenAI SDK failed, falling back to LangChain: {e}")

            response = await self.client.ainvoke(messages, **kwargs)

            # Normalize content
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            result = str(content).strip() if content else "죄송합니다. 응답을 생성하지 못했습니다."

            # Extract token usage
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = response.usage_metadata.get("input_tokens", 0)
                output_tokens = response.usage_metadata.get("output_tokens", 0)
            elif hasattr(response, "response_metadata") and response.response_metadata:
                usage = response.response_metadata.get("token_usage", {})
                input_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)

        # Cache the response
        await self._cache.set(
            messages=messages,
            model=self.config.model,
            temperature=self.config.temperature,
            response=result,
        )

        return result, {"input_tokens": input_tokens, "output_tokens": output_tokens}

    def _safe_int(self, value) -> int:
        """Safely convert header value to int."""
        if value is None:
            return -1
        try:
            return int(value)
        except (ValueError, TypeError):
            return -1

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
