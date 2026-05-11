"""Tests for conversation memory command module."""

import pytest

from src.agents.conversation_memory import ConversationMemoryCommands
from src.memory.in_memory_store import InMemoryStore


class FakeLongTermMemory:
    def __init__(self):
        self.facts = []

    async def store_user_fact(self, user_id, fact, category="general", confidence=1.0):
        self.facts.append(
            {
                "user_id": user_id,
                "fact": fact,
                "category": category,
                "confidence": confidence,
            }
        )

    async def search_similar_facts(self, user_id, query):
        return [fact for fact in self.facts if fact["user_id"] == user_id and query in fact["fact"]]


@pytest.mark.asyncio
async def test_remember_stores_session_and_long_term_fact():
    memory = InMemoryStore()
    long_term_memory = FakeLongTermMemory()
    commands = ConversationMemoryCommands(memory=memory, long_term_memory=long_term_memory)

    command = commands.parse("기억해: 저는 짧은 답변을 선호합니다")
    response = await commands.handle("session-1", "user-1", command)

    assert response == "기억했습니다: 저는 짧은 답변을 선호합니다"
    session_messages = await memory.get_messages("session-1")
    assert session_messages[0]["type"] == "explicit_memory"
    assert long_term_memory.facts == [
        {
            "user_id": "user-1",
            "fact": "저는 짧은 답변을 선호합니다",
            "category": "general",
            "confidence": 1.0,
        }
    ]


@pytest.mark.asyncio
async def test_recall_uses_long_term_query_matches():
    memory = InMemoryStore()
    long_term_memory = FakeLongTermMemory()
    commands = ConversationMemoryCommands(memory=memory, long_term_memory=long_term_memory)
    await long_term_memory.store_user_fact("user-1", "Python 예제를 선호합니다")

    command = commands.parse("알고 있니? Python")
    response = await commands.handle("session-1", "user-1", command)

    assert "Python 예제를 선호합니다" in response
