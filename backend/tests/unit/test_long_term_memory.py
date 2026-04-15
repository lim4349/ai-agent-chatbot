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
