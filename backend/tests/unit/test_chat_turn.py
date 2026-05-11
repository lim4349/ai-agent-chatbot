"""Tests for chat turn intake helpers."""

import pytest

from src.api.chat_turn import prepare_chat_turn, resolve_agent_used


class FakeSession:
    user_id = "device-from-session"


class FakeSessionStore:
    async def get(self, session_id):
        return FakeSession()


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    async def has_documents_for_session(self, device_id, session_id):
        self.calls.append({"device_id": device_id, "session_id": session_id})
        return True


@pytest.mark.asyncio
async def test_prepare_chat_turn_resolves_device_and_document_availability():
    vector_store = FakeVectorStore()

    turn = await prepare_chat_turn(
        sanitized_message="문서에서 찾아줘",
        session_id="session-1",
        request_device_id=None,
        path="/api/v1/chat",
        vector_store=vector_store,
        session_store=FakeSessionStore(),
        tool_registry=None,
    )

    assert turn.device_id == "device-from-session"
    assert turn.has_documents is True
    assert turn.initial_state["metadata"]["device_id"] == "device-from-session"
    assert turn.initial_state["has_documents"] is True
    assert vector_store.calls == [
        {"device_id": "device-from-session", "session_id": "session-1"}
    ]


def test_resolve_agent_used_prefers_completed_steps():
    assert resolve_agent_used({"completed_steps": ["chat", "research"], "next_agent": "chat"}) == "research"
