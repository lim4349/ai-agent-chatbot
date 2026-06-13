"""Tests for shared LLM invocation contracts."""

import pytest
from pydantic import BaseModel

from src.core.config import LLMConfig
from src.llm import invocation
from src.llm.invocation import (
    generate_with_cache,
    invoke_with_retry,
    parse_json_response,
    validate_structured_result,
)
from src.llm.openai_provider import OpenAIProvider


class FakeResponse:
    content = " generated "
    usage_metadata = {"input_tokens": 7, "output_tokens": 3}


class FakeCache:
    def __init__(self, cached=None):
        self.cached = cached
        self.set_calls = []

    async def get(self, **kwargs):
        return self.cached

    async def set(self, **kwargs):
        self.set_calls.append(kwargs)


class FakeClient:
    def __init__(self, failures=0, message="rate limit 429"):
        self.failures = failures
        self.message = message
        self.calls = 0

    async def ainvoke(self, messages, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError(self.message)
        return FakeResponse()


class ToolChoice(BaseModel):
    tools: list[str]
    response_mode: str


@pytest.mark.asyncio
async def test_invoke_with_retry_retries_transient_errors(monkeypatch):
    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(invocation.asyncio, "sleep", no_sleep)
    client = FakeClient(failures=2)

    response = await invoke_with_retry(client, [{"role": "user", "content": "hi"}])

    assert isinstance(response, FakeResponse)
    assert client.calls == 3


@pytest.mark.asyncio
async def test_invoke_with_retry_does_not_retry_non_transient_errors(monkeypatch):
    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(invocation.asyncio, "sleep", no_sleep)
    client = FakeClient(failures=1, message="invalid request")

    with pytest.raises(RuntimeError, match="invalid request"):
        await invoke_with_retry(client, [{"role": "user", "content": "hi"}])

    assert client.calls == 1


@pytest.mark.asyncio
async def test_generate_with_cache_returns_cached_text_without_client_call():
    cache = FakeCache(cached="cached answer")
    client = FakeClient()
    config = LLMConfig(provider="openai", model="mock", temperature=0.1)

    content, usage = await generate_with_cache(
        cache=cache,
        client=client,
        config=config,
        messages=[{"role": "user", "content": "hi"}],
    )

    assert content == "cached answer"
    assert usage == {"input_tokens": 0, "output_tokens": 0}
    assert client.calls == 0
    assert cache.set_calls == []


@pytest.mark.asyncio
async def test_generate_with_cache_normalizes_and_stores_response():
    cache = FakeCache()
    client = FakeClient()
    config = LLMConfig(provider="openai", model="mock", temperature=0.1)

    content, usage = await generate_with_cache(
        cache=cache,
        client=client,
        config=config,
        messages=[{"role": "user", "content": "hi"}],
    )

    assert content == "generated"
    assert usage == {"input_tokens": 7, "output_tokens": 3}
    assert cache.set_calls[0]["response"] == "generated"


def test_parse_json_response_handles_markdown_and_mixed_text():
    assert parse_json_response('```json\n{"tools":["retriever"]}\n```') == {
        "tools": ["retriever"]
    }
    assert parse_json_response('answer\n{"response_mode":"answer"}') == {
        "response_mode": "answer"
    }
    assert parse_json_response("not json") is None


def test_validate_structured_result_checks_pydantic_schema():
    assert validate_structured_result(
        {"tools": ["retriever"], "response_mode": "answer"},
        ToolChoice,
    ) == {"tools": ["retriever"], "response_mode": "answer"}
    assert validate_structured_result({"tools": ["retriever"]}, ToolChoice) is None


def test_openrouter_provider_sets_zero_max_price_guard(monkeypatch):
    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeCacheProvider:
        def __call__(self):
            return FakeCache()

    monkeypatch.setattr("src.llm.openai_provider.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("src.llm.openai_provider.container.llm_cache", FakeCacheProvider())

    provider = OpenAIProvider(
        LLMConfig(
            provider="openai",
            model="openrouter/free",
            base_url="https://openrouter.ai/api/v1",
            openai_api_key="test-key",
        )
    )

    assert provider.client.kwargs["extra_body"] == {
        "max_price": {"input": 0, "output": 0}
    }


@pytest.mark.asyncio
async def test_openai_provider_structured_output_falls_back_to_text_json(monkeypatch):
    class FailingStructured:
        async def ainvoke(self, messages, **kwargs):
            raise RuntimeError("structured output unsupported")

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def with_structured_output(self, output_schema):
            return FailingStructured()

        async def ainvoke(self, messages, **kwargs):
            response = FakeResponse()
            response.content = '```json\n{"tools":["retriever"],"response_mode":"answer"}\n```'
            return response

    class FakeCacheProvider:
        def __call__(self):
            return FakeCache()

    monkeypatch.setattr("src.llm.openai_provider.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("src.llm.openai_provider.container.llm_cache", FakeCacheProvider())

    provider = OpenAIProvider(
        LLMConfig(provider="openai", model="mock", openai_api_key="test-key")
    )

    result = await provider.generate_structured(
        [{"role": "user", "content": "choose tools"}],
        output_schema=ToolChoice,
    )

    assert result == {"tools": ["retriever"], "response_mode": "answer"}


@pytest.mark.asyncio
async def test_openai_provider_structured_output_returns_none_for_bad_fallback_json(
    monkeypatch,
):
    class EmptyStructured:
        async def ainvoke(self, messages, **kwargs):
            return None

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def with_structured_output(self, output_schema):
            return EmptyStructured()

        async def ainvoke(self, messages, **kwargs):
            response = FakeResponse()
            response.content = "not json"
            return response

    class FakeCacheProvider:
        def __call__(self):
            return FakeCache()

    monkeypatch.setattr("src.llm.openai_provider.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("src.llm.openai_provider.container.llm_cache", FakeCacheProvider())

    provider = OpenAIProvider(
        LLMConfig(provider="openai", model="mock", openai_api_key="test-key")
    )

    result = await provider.generate_structured(
        [{"role": "user", "content": "choose tools"}],
        output_schema=dict,
    )

    assert result is None
