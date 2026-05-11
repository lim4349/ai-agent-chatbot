"""Shared LLM invocation helpers for provider adapters."""

from __future__ import annotations

import json
import re
import warnings
from typing import Any

from src.observability.agent_metrics import extract_token_usage_from_response

DEFAULT_EMPTY_RESPONSE = "죄송합니다. 응답을 생성하지 못했습니다."


def normalize_content(content: Any, *, strip: bool = True) -> str:
    """Normalize provider-specific content blocks into text."""
    if isinstance(content, list):
        content = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    if not content:
        return DEFAULT_EMPTY_RESPONSE if strip else ""
    text = str(content)
    return text.strip() if strip else text


async def generate_with_cache(
    *,
    cache,
    client,
    config,
    messages: list[dict[str, str]],
    **kwargs,
) -> tuple[str, dict[str, int]]:
    """Run a non-streaming chat invocation with cache and token usage."""
    cached = await cache.get(
        messages=messages,
        model=config.model,
        temperature=config.temperature,
    )
    if cached is not None:
        return cached, {"input_tokens": 0, "output_tokens": 0}

    response = await client.ainvoke(messages, **kwargs)
    result = normalize_content(response.content)
    input_tokens, output_tokens = extract_token_usage_from_response(response)

    await cache.set(
        messages=messages,
        model=config.model,
        temperature=config.temperature,
        response=result,
    )

    return result, {"input_tokens": input_tokens, "output_tokens": output_tokens}


def extract_structured_result(result) -> dict | None:
    """Extract structured data from LangChain wrappers or Pydantic models."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)

        if hasattr(result, "parsed") and result.parsed is not None:
            inner = result.parsed
            if hasattr(inner, "model_dump"):
                return inner.model_dump()
            if isinstance(inner, dict):
                return inner
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


def parse_json_response(content: str) -> dict | None:
    """Parse a JSON object from direct text, markdown blocks, or mixed text."""
    if not content:
        return None

    content = content.strip()

    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
    if code_block_match:
        try:
            result = json.loads(code_block_match.group(1).strip())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    object_match = re.search(r"\{[\s\S]*\}", content)
    if object_match:
        try:
            result = json.loads(object_match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return None
