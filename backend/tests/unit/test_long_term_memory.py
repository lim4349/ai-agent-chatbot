"""Tests for long-term memory storage policy."""

import pytest

from src.memory.long_term_memory import LongTermMemory


@pytest.mark.asyncio
async def test_store_user_fact_skips_low_confidence_and_dedupes():
    """Facts should be filtered for quality and deduped per category."""
    memory = LongTermMemory(anonymize=True)

    await memory.store_user_fact(
        user_id="device-1",
        fact="Prefers concise answers in bullet points.",
        category="preferences",
        confidence=0.91,
    )
    await memory.store_user_fact(
        user_id="device-1",
        fact="prefers concise answers in bullet points",
        category="preferences",
        confidence=0.95,
    )
    await memory.store_user_fact(
        user_id="device-1",
        fact="Likes it",
        category="preferences",
        confidence=0.4,
    )

    facts = memory._facts["device-1"]
    assert len(facts) == 1
    assert facts[0]["confidence"] == 0.95


@pytest.mark.asyncio
async def test_store_topic_summary_replaces_same_session_topic_and_anonymizes():
    """Topic summaries should upsert by session/topic and redact obvious identifiers."""
    memory = LongTermMemory(anonymize=True)

    await memory.store_topic_summary(
        topic="deployment issue",
        summary="Investigated failure for user@example.com at https://internal.example.com/run/123.",
        session_id="session-1",
    )
    await memory.store_topic_summary(
        topic="deployment issue",
        summary="Investigated deployment retries for @ops and narrowed it to health-check startup timing.",
        session_id="session-1",
    )

    history = await memory.get_topic_history("deployment issue")
    assert len(history) == 1
    assert "[EMAIL_REDACTED]" not in history[0]["summary"]
    assert "[URL_REDACTED]" not in history[0]["summary"]
    assert "[HANDLE_REDACTED]" in history[0]["summary"]
    assert "health-check startup timing" in history[0]["summary"]


def test_anonymize_redacts_common_identifiers():
    """Anonymization should redact common high-risk identifiers."""
    memory = LongTermMemory(anonymize=True)

    redacted = memory._anonymize(
        "Email user@example.com, visit https://example.com, ping 10.0.0.4, notify @ops, see ABC-123."
    )

    assert "[EMAIL_REDACTED]" in redacted
    assert "[URL_REDACTED]" in redacted
    assert "[IP_REDACTED]" in redacted
    assert "[HANDLE_REDACTED]" in redacted
    assert "[TICKET_REDACTED]" in redacted


@pytest.mark.asyncio
async def test_delete_session_topics_preserves_user_facts_and_other_sessions():
    """Session cleanup should remove only session-scoped topic memory."""
    memory = LongTermMemory(anonymize=True)

    await memory.store_user_fact(
        user_id="device-1",
        fact="Prefers concise technical explanations.",
        category="preferences",
        confidence=0.95,
    )
    await memory.store_topic_summary(
        topic="rag lifecycle",
        summary="Session one discussed upload, retrieval, and deletion behavior.",
        session_id="session-1",
    )
    await memory.store_topic_summary(
        topic="rag lifecycle",
        summary="Session two discussed dashboard observability and metrics.",
        session_id="session-2",
    )

    deleted_count = await memory.delete_session_topics("session-1")

    assert deleted_count == 1
    assert await memory.get_session_topic_names("session-1") == set()
    assert await memory.get_session_topic_names("session-2") == {"rag lifecycle"}
    assert memory._facts["device-1"][0]["fact"] == "Prefers concise technical explanations."

    history = await memory.get_topic_history("rag lifecycle")
    assert [entry["session_id"] for entry in history] == ["session-2"]


@pytest.mark.asyncio
async def test_clear_user_data_preserves_session_topics():
    """User memory cleanup should not delete session-scoped topic summaries."""
    memory = LongTermMemory(anonymize=True)

    await memory.store_user_fact(
        user_id="device-1",
        fact="Prefers concise technical explanations.",
        category="preferences",
        confidence=0.95,
    )
    await memory.store_topic_summary(
        topic="rag lifecycle",
        summary="Session one discussed upload, retrieval, and deletion behavior.",
        session_id="session-1",
    )

    await memory.clear_user_data("device-1")

    assert "device-1" not in memory._facts
    assert await memory.get_session_topic_names("session-1") == {"rag lifecycle"}
