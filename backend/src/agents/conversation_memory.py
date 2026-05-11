"""Conversation memory command handling for the chat agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.core.logging import get_logger
from src.core.protocols import MemoryStore, Summarizer

if TYPE_CHECKING:
    from src.memory.long_term_memory import LongTermMemory

logger = get_logger(__name__)


@dataclass(frozen=True)
class MemoryCommand:
    """Parsed memory command from a user message."""

    type: str
    data: str | None = None


class ConversationMemoryCommands:
    """Owns memory command parsing and execution."""

    COMMAND_REMEMBER = "기억해:"
    COMMAND_REMEMBER_ALT = "기억해줘:"
    COMMAND_RECALL = "알고 있니?"
    COMMAND_FORGET = "잊어줘:"
    COMMAND_SUMMARIZE = "요약해줘"

    def __init__(
        self,
        *,
        memory: MemoryStore | None,
        long_term_memory: LongTermMemory | None = None,
        summarizer: Summarizer | None = None,
    ) -> None:
        self.memory = memory
        self.long_term_memory = long_term_memory
        self.summarizer = summarizer

    def parse(self, content: str) -> MemoryCommand:
        """Parse user message for supported memory commands."""
        content_stripped = content.strip()

        if content_stripped.startswith(self.COMMAND_REMEMBER):
            data = content_stripped[len(self.COMMAND_REMEMBER) :].strip()
            return MemoryCommand("remember", data)
        if content_stripped.startswith(self.COMMAND_REMEMBER_ALT):
            data = content_stripped[len(self.COMMAND_REMEMBER_ALT) :].strip()
            return MemoryCommand("remember", data)

        if self.COMMAND_RECALL in content_stripped:
            parts = content_stripped.split(self.COMMAND_RECALL, 1)
            query = parts[1].strip() if len(parts) > 1 else None
            return MemoryCommand("recall", query)

        if content_stripped.startswith(self.COMMAND_FORGET):
            data = content_stripped[len(self.COMMAND_FORGET) :].strip()
            return MemoryCommand("forget", data)

        if self.COMMAND_SUMMARIZE in content_stripped:
            return MemoryCommand("summarize")

        return MemoryCommand("none")

    async def handle(self, session_id: str, user_id: str | None, command: MemoryCommand) -> str | None:
        """Execute a parsed memory command."""
        if command.type == "remember":
            return await self._handle_remember(session_id, user_id, command.data or "")
        if command.type == "recall":
            return await self._handle_recall(session_id, user_id, command.data)
        if command.type == "forget":
            return await self._handle_forget(session_id, command.data or "")
        if command.type == "summarize":
            return await self._handle_summarize(session_id)
        return None

    async def _handle_remember(self, session_id: str, user_id: str | None, data: str) -> str:
        """Store an explicit user fact in session and long-term memory."""
        if not self.memory:
            return "메모리 기능을 사용할 수 없습니다. (Memory not available)"

        fact_message = {
            "role": "user_fact",
            "content": data,
            "weight": 0.9,
            "type": "explicit_memory",
        }
        await self.memory.add_message(session_id, fact_message)

        if user_id and self.long_term_memory:
            await self.long_term_memory.store_user_fact(
                user_id=user_id,
                fact=data,
                category="general",
                confidence=1.0,
            )

        logger.info("user_fact_stored", session_id=session_id, user_id=user_id, fact=data)
        return f"기억했습니다: {data}"

    async def _handle_recall(
        self,
        session_id: str,
        user_id: str | None,
        query: str | None,
    ) -> str:
        """Retrieve relevant explicit memories."""
        if not self.memory:
            return "메모리 기능을 사용할 수 없습니다. (Memory not available)"

        try:
            relevant = await self._session_relevant_messages(session_id)

            if user_id and self.long_term_memory and query:
                for fact in await self.long_term_memory.search_similar_facts(user_id, query):
                    relevant.append(
                        {
                            "content": fact.get("fact", ""),
                            "type": "explicit_memory",
                            "weight": fact.get("confidence", 0.8),
                        }
                    )

            if not relevant:
                return "아직 기억에 저장된 내용이 없습니다."

            memories_text = []
            for msg in relevant[-5:]:
                content = msg.get("content", "")
                msg_type = msg.get("type", "")
                if msg_type == "explicit_memory":
                    memories_text.append(f"- [중요] {content}")
                else:
                    memories_text.append(f"- {content[:100]}...")

            return "기억하고 있는 내용:\n" + "\n".join(memories_text)

        except Exception as e:
            logger.error("recall_failed", error=str(e), session_id=session_id)
            return "기억을 불러오는 중 오류가 발생했습니다."

    async def _session_relevant_messages(self, session_id: str) -> list[dict]:
        """Return high-value session memory messages."""
        if not self.memory:
            return []

        messages = await self.memory.get_messages(session_id)
        relevant = []
        for msg in messages:
            weight = msg.get("weight", 0.5)
            msg_type = msg.get("type", "")
            if not msg.get("deleted") and (weight >= 0.7 or msg_type == "explicit_memory"):
                relevant.append(msg)
        return relevant

    async def _handle_forget(self, session_id: str, data: str) -> str:
        """Mark matching session memory as deleted."""
        if not self.memory:
            return "메모리 기능을 사용할 수 없습니다. (Memory not available)"

        try:
            messages = await self.memory.get_messages(session_id)
            removed = False

            for i, msg in enumerate(messages):
                content = msg.get("content", "")
                if data.lower() in content.lower():
                    msg["deleted"] = True
                    msg["weight"] = 0.0
                    removed = True
                    logger.info("message_marked_deleted", session_id=session_id, index=i)

            if removed:
                return f"'{data}'와 관련된 내용을 잊었습니다."
            return f"'{data}'와 일치하는 내용을 찾을 수 없습니다."

        except Exception as e:
            logger.error("forget_failed", error=str(e), session_id=session_id)
            return "기억을 삭제하는 중 오류가 발생했습니다."

    async def _handle_summarize(self, session_id: str) -> str:
        """Trigger manual summarization."""
        if not self.memory:
            return "메모리 기능을 사용할 수 없습니다. (Memory not available)"
        if not self.summarizer:
            return "요약 기능을 사용할 수 없습니다. (Summarizer not available)"

        try:
            messages = await self.memory.get_messages(session_id)
            if len(messages) < 3:
                return "요약할 대화 내용이 충분하지 않습니다. (최소 3개 메시지 필요)"

            result = await self.summarizer.check_and_summarize(session_id, messages)
            if result:
                return f"대화를 요약했습니다:\n{result.get('summary', '')}"
            return "요약을 생성할 수 없습니다."

        except Exception as e:
            logger.error("summarize_failed", error=str(e), session_id=session_id)
            return "요약하는 중 오류가 발생했습니다."
