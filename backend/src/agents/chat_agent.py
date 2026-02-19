"""Chat agent for general conversation."""

from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore, Summarizer, TopicMemory, UserProfiler
from src.graph.state import AgentState
from src.memory.long_term_memory import LongTermMemory

logger = get_logger(__name__)


def message_to_dict(msg) -> dict:
    """Convert LangChain message to dict format."""
    if isinstance(msg, dict):
        return msg
    if isinstance(msg, BaseMessage):
        return {"role": msg.type, "content": msg.content}
    return {"role": "user", "content": str(msg)}


class ChatAgent(BaseAgent):
    """General conversation agent with memory support."""

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "chat"

    # Memory command prefixes
    COMMAND_REMEMBER = "기억해:"
    COMMAND_REMEMBER_ALT = "기억해줘:"
    COMMAND_RECALL = "알고 있니?"
    COMMAND_FORGET = "잊어줘:"
    COMMAND_SUMMARIZE = "요약해줘"

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        memory: MemoryStore = Provide[DIContainer.memory],
        long_term_memory: LongTermMemory | None = Provide[DIContainer.long_term_memory],
        user_profiler: UserProfiler | None = Provide[DIContainer.user_profiler],
        topic_memory: TopicMemory | None = Provide[DIContainer.topic_memory],
        summarizer: Summarizer | None = Provide[DIContainer.summarizer],
    ):
        super().__init__(llm)
        self.memory = memory
        self.long_term_memory = long_term_memory
        self.user_profiler = user_profiler
        self.topic_memory = topic_memory
        self.summarizer = summarizer
        self._user_profiles: dict[str, dict] = {}

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        return (
            """You are a helpful, friendly AI assistant. You engage in natural conversation and provide thoughtful, informative responses.

Guidelines:
- Be conversational but professional
- Provide helpful and accurate information
- If you don't know something, admit it honestly
- Be concise but thorough when appropriate
- Show empathy and understanding in your responses

Formatting Rules (IMPORTANT):
- ALWAYS use proper line breaks between list items
- Format lists as:
  - item 1
  - item 2
  - item 3
- NEVER put multiple list items on the same line
- ALWAYS separate URLs from Korean text with a space
- Format URLs properly: https://www.example.com (no spaces in domain)
- Example:
  Wrong: "주가는 다음과 같습니다- 136.31달러 (출처: https://www.example.com)- 142.91달러"
  Right: "주가는 다음과 같습니다\n- 136.31달러 (출처: https://www.example.com)\n- 142.91달러\"""",
        )

    def _parse_memory_command(self, content: str) -> tuple[str, str | None]:
        """Parse user message for memory commands.

        Args:
            content: The user message content

        Returns:
            Tuple of (command_type, command_data)
        """
        content_stripped = content.strip()

        # Check for "기억해:" or "기억해줘:" (Remember)
        if content_stripped.startswith(self.COMMAND_REMEMBER):
            data = content_stripped[len(self.COMMAND_REMEMBER) :].strip()
            return ("remember", data)
        if content_stripped.startswith(self.COMMAND_REMEMBER_ALT):
            data = content_stripped[len(self.COMMAND_REMEMBER_ALT) :].strip()
            return ("remember", data)

        # Check for "알고 있니?" (Recall)
        if self.COMMAND_RECALL in content_stripped:
            # Extract query after the command if any
            parts = content_stripped.split(self.COMMAND_RECALL, 1)
            query = parts[1].strip() if len(parts) > 1 else None
            return ("recall", query)

        # Check for "잊어줘:" (Forget)
        if content_stripped.startswith(self.COMMAND_FORGET):
            data = content_stripped[len(self.COMMAND_FORGET) :].strip()
            return ("forget", data)

        # Check for "요약해줘" (Summarize)
        if self.COMMAND_SUMMARIZE in content_stripped:
            return ("summarize", None)

        return ("none", None)

    async def _handle_remember(self, session_id: str, data: str) -> str:
        """Handle remember command - store user fact.

        Args:
            session_id: The session identifier
            data: The fact to remember

        Returns:
            Confirmation message
        """
        if not self.memory:
            return "메모리 기능을 사용할 수 없습니다. (Memory not available)"

        # Store as a special user fact with high weight
        fact_message = {
            "role": "user_fact",
            "content": data,
            "weight": 0.9,  # High weight for explicit user facts
            "type": "explicit_memory",
        }

        await self.memory.add_message(session_id, fact_message)
        logger.info("user_fact_stored", session_id=session_id, fact=data)

        return f"기억했습니다: {data}"

    async def _handle_recall(self, session_id: str, query: str | None) -> str:
        """Handle recall command - retrieve relevant memories.

        Args:
            session_id: The session identifier
            query: Optional specific query

        Returns:
            Retrieved memories or message
        """
        if not self.memory:
            return "메모리 기능을 사용할 수 없습니다. (Memory not available)"

        try:
            messages = await self.memory.get_messages(session_id)

            if not messages:
                return "아직 기억에 저장된 내용이 없습니다."

            # Filter for high-weight messages and user facts
            relevant = []
            for msg in messages:
                weight = msg.get("weight", 0.5)
                msg_type = msg.get("type", "")
                if weight >= 0.7 or msg_type == "explicit_memory":
                    relevant.append(msg)

            if not relevant:
                return "특별히 기억할 만한 내용이 없습니다."

            # Format memories
            memories_text = []
            for msg in relevant[-5:]:  # Last 5 relevant memories
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

    async def _handle_forget(self, session_id: str, data: str) -> str:
        """Handle forget command - remove specific memory.

        Args:
            session_id: The session identifier
            data: The memory to forget (partial match)

        Returns:
            Confirmation message
        """
        if not self.memory:
            return "메모리 기능을 사용할 수 없습니다. (Memory not available)"

        try:
            messages = await self.memory.get_messages(session_id)
            removed = False

            # Find and remove matching messages
            for i, msg in enumerate(messages):
                content = msg.get("content", "")
                if data.lower() in content.lower():
                    # Mark as removed
                    msg["deleted"] = True
                    msg["weight"] = 0.0
                    removed = True
                    logger.info("message_marked_deleted", session_id=session_id, index=i)

            if removed:
                return f"'{data}'와 관련된 내용을 잊었습니다."
            else:
                return f"'{data}'와 일치하는 내용을 찾을 수 없습니다."

        except Exception as e:
            logger.error("forget_failed", error=str(e), session_id=session_id)
            return "기억을 삭제하는 중 오류가 발생했습니다."

    async def _handle_summarize(self, session_id: str) -> str:
        """Handle summarize command - trigger manual summarization.

        Args:
            session_id: The session identifier

        Returns:
            Summary or message
        """
        if not self.memory:
            return "메모리 기능을 사용할 수 없습니다. (Memory not available)"

        if not self.summarizer:
            return "요약 기능을 사용할 수 없습니다. (Summarizer not available)"

        try:
            messages = await self.memory.get_messages(session_id)

            if len(messages) < 3:
                return "요약할 대화 내용이 충분하지 않습니다. (최소 3개 메시지 필요)"

            # Trigger summarization
            result = await self.summarizer.check_and_summarize(session_id, messages)

            if result:
                return f"대화를 요약했습니다:\n{result.get('summary', '')}"
            else:
                return "요약을 생성할 수 없습니다."

        except Exception as e:
            logger.error("summarize_failed", error=str(e), session_id=session_id)
            return "요약하는 중 오류가 발생했습니다."

    async def _handle_memory_command(
        self, session_id: str, command_type: str, command_data: str | None
    ) -> str | None:
        """Handle memory commands.

        Args:
            session_id: The session identifier
            command_type: Type of command
            command_data: Optional command data

        Returns:
            Response string or None if not a command
        """
        if command_type == "remember":
            return await self._handle_remember(session_id, command_data or "")
        elif command_type == "recall":
            return await self._handle_recall(session_id, command_data)
        elif command_type == "forget":
            return await self._handle_forget(session_id, command_data or "")
        elif command_type == "summarize":
            return await self._handle_summarize(session_id)
        else:
            return None

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Generate a conversational response."""
        session_id = state.get("metadata", {}).get("session_id", "default")
        user_id = state.get("metadata", {}).get("user_id")

        # Get the last user message and check for memory commands
        last_msg = state["messages"][-1]
        last_content = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)

        # Check for memory commands
        command_type, command_data = self._parse_memory_command(last_content)

        if command_type != "none":
            # Handle memory command
            response = await self._handle_memory_command(session_id, command_type, command_data)

            # Store the command and response
            if self.memory:
                await self.memory.add_message(session_id, message_to_dict(last_msg))
                await self.memory.add_message(
                    session_id, {"role": "assistant", "content": response}
                )

            return {
                **state,
                "messages": [*state["messages"], {"role": "assistant", "content": response}],
            }

        # Build messages with system prompt
        system_content = self.system_prompt

        # Load user profile and add personalization
        if user_id and self.user_profiler:
            profile = await self._get_user_profile(user_id)
            if profile:
                personalization = self.user_profiler.get_personalization_context(profile)
                if personalization:
                    system_content += f"\n\n{personalization}"

        # Add topic context for cross-session continuity
        if self.topic_memory and user_id:
            topic_context = await self.topic_memory.get_cross_session_context(
                session_id,
                [message_to_dict(m) for m in state["messages"]],
            )
            if topic_context:
                system_content += f"\n\n{topic_context}"

        messages = [{"role": "system", "content": system_content}]

        # Add conversation history from short-term memory
        if self.memory:
            history = await self.memory.get_messages(session_id)
            messages.extend(history)

        # Convert LangChain messages to dict format
        current_messages = [message_to_dict(msg) for msg in state["messages"]]
        messages.extend(current_messages)

        # Generate response
        response = await self.llm.generate(messages)

        # Store in short-term memory
        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        # Extract and save user facts
        if user_id and self.user_profiler:
            await self._extract_user_facts(user_id, current_messages)

        # Process topics for cross-session linking
        if self.topic_memory and user_id:
            await self._process_topics(session_id, current_messages)

        return {
            **state,
            "messages": [
                *state["messages"],
                {"role": "assistant", "content": response},
            ],
        }

    async def _get_user_profile(self, user_id: str):
        """Get user profile from cache or long-term memory."""
        if user_id in self._user_profiles:
            return self._user_profiles[user_id]

        if self.user_profiler:
            profile = await self.user_profiler.get_profile(user_id)
            if profile:
                self._user_profiles[user_id] = profile
            return profile

        return None

    async def _extract_user_facts(self, user_id: str, messages: list[dict]) -> None:
        """Extract and save facts about the user."""
        if not self.user_profiler or not self.long_term_memory:
            return

        try:
            # Update profile incrementally
            if messages:
                await self.user_profiler.update_from_message(
                    user_id,
                    messages[-1],
                    messages[:-1] if len(messages) > 1 else None,
                )
        except Exception as e:
            logger.error("fact_extraction_failed", error=str(e), user_id=user_id)

    async def _process_topics(self, session_id: str, messages: list[dict]) -> None:
        """Process and store topics from conversation."""
        if not self.topic_memory:
            return

        try:
            # Process topics periodically (every 5 messages)
            if len(messages) >= 5 and len(messages) % 5 == 0:
                await self.topic_memory.process_session_topics(session_id, messages)
        except Exception as e:
            logger.error("topic_processing_failed", error=str(e), session_id=session_id)
