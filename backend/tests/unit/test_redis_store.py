"""Tests for Redis memory store fallback behavior."""

import pytest

from src.memory.redis_store import RedisStore


class FailingRedisClient:
    """Redis client stub that fails connectivity checks."""

    async def ping(self):
        raise OSError("dns resolution failed")


@pytest.mark.asyncio
async def test_redis_store_falls_back_to_in_memory_on_ping_failure(monkeypatch):
    """Redis outages should not break chat memory operations."""
    monkeypatch.setattr(
        "src.memory.redis_store.redis.from_url",
        lambda *_args, **_kwargs: FailingRedisClient(),
    )

    store = RedisStore("rediss://default:secret@example.upstash.io:6379")

    await store.add_message("session-1", {"role": "user", "content": "hello"})
    messages = await store.get_messages("session-1")

    assert store._fallback_enabled is True
    assert messages == [{"role": "user", "content": "hello"}]


def test_masked_url_hides_credentials():
    """Credential-bearing Redis URLs should not be logged verbatim."""
    store = RedisStore("rediss://default:supersecret@example.upstash.io:6379")

    assert store._masked_url() == "rediss://default:[REDACTED]@example.upstash.io:6379"
