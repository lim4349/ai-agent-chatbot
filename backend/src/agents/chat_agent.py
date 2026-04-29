"""Chat agent for general conversation."""

import asyncio
from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore, Summarizer, TopicMemory, UserProfiler
from src.graph.state import AgentState
from src.memory.long_term_memory import LongTermMemory
from src.observability import record_agent_metrics

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
        metrics_store=Provide[DIContainer.metrics_store],
        search_tool=None,
        retriever=None,
    ):
        super().__init__(llm)
        self.memory = memory
        self.long_term_memory = long_term_memory
        self.user_profiler = user_profiler
        self.topic_memory = topic_memory
        self.summarizer = summarizer
        self.metrics_store = metrics_store
        self.search_tool = search_tool
        self.retriever = retriever
        self._user_profiles: dict[str, dict] = {}

    def _get_capability_context(self, available_agents: list[str] | None) -> str:
        """Generate capability context based on available agents.

        Args:
            available_agents: List of available agent names

        Returns:
            Capability context string for system prompt
        """
        if not available_agents:
            return ""

        has_code = "code" in available_agents
        has_web_search = "web_search" in available_agents

        context_parts = []

        if not has_code:
            context_parts.append("""
## Code Execution Unavailable
- Code execution is disabled in this environment
- When users ask for code execution, calculations, or programming tasks:
  - Offer to explain the algorithm or logic instead
  - Suggest using web search for reference implementations
  - Provide manual calculations when feasible
  - Example response: "코드 실행 기능이 현재 비활성화되어 있습니다. 대신 알고리즘을 설명해 드릴까요? 또는 웹 검색으로 관련 자료를 찾아드릴까요?"
""")

        if not has_web_search:
            context_parts.append("""
## Web Search Unavailable
- Web search is disabled in this environment
- When users ask for current information or real-time data:
  - Acknowledge the limitation
  - Provide general knowledge if available
  - Suggest alternative sources
""")

        return "\n".join(context_parts)

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        return """You are a helpful, friendly AI assistant. You engage in natural conversation and provide thoughtful, informative responses.

Guidelines:
- Be conversational but professional
- Provide helpful and accurate information
- If you don't know something, admit it honestly
- Be concise but thorough when appropriate
- Show empathy and understanding in your responses

# 응답 형식 규칙 (CommonMark 마크다운 표준 준수)

## 문장 작성 규칙
- 문장 끝 마침표(., !, ?) 뒤에는 반드시 공백 한 칸 추가
- 한 문장이 끝나면 다음 문장은 새로 시작 (같은 줄에 이어쓰기 금지)

## 제목/소주제 작성
- 주제 변경 시 반드시 줄바꿈으로 구분
- 소주제 앞뒤로 빈 줄 추가

## 목록 작성 (CRITICAL)
- 모든 목록 항목은 반드시 새 줄에 작성
- 순서 없는 목록: "- " (하이픈 + 공백)으로 시작
- 순서 있는 목록: "1. " "2. " 형식으로 시작
- 목록 앞뒤로 반드시 빈 줄 추가
- 절대 한 줄에 여러 목록 항목 작성 금지

올바른 예시:
```
내용입니다.

- 항목 1
- 항목 2
- 항목 3

다음 내용입니다.
```

잘못된 예시:
```
내용입니다.- 항목 1- 항목 2
```
"""

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

        # Add capability context based on available agents
        available_agents = state.get("available_agents")
        capability_context = self._get_capability_context(available_agents)
        if capability_context:
            system_content += f"\n\n{capability_context}"

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

        # Tool pre-fetching based on tools_hint (parallel, before LLM call)
        tools_hint = state.get("tools_hint", [])
        tool_context_parts = []
        tool_results = []

        if tools_hint:
            query = last_content
            metadata = state.get("metadata", {})
            tool_session_id = metadata.get("session_id", session_id)
            device_id = metadata.get("device_id") or metadata.get("user_id")

            tasks = []
            if "web_search" in tools_hint and self.search_tool:
                tasks.append(("web_search", self.search_tool.execute(query)))
            if "retriever" in tools_hint and self.retriever and state.get("has_documents"):
                tasks.append(
                    (
                        "retriever",
                        self.retriever.execute(
                            query,
                            top_k=3,
                            session_id=tool_session_id,
                            device_id=device_id,
                        ),
                    )
                )

            if tasks:
                results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
                for (tool_name, _), result in zip(tasks, results, strict=True):
                    if isinstance(result, Exception):
                        logger.warning("tool_failed", tool=tool_name, error=str(result))
                        continue
                    if tool_name == "web_search":
                        tool_context_parts.append(f"## 웹 검색 결과\n{result}")
                        tool_results.append({"tool": "web_search", "query": query, "results": result})
                    elif tool_name == "retriever":
                        docs_text = "\n\n".join(
                            f"[{d.get('metadata', {}).get('source', 'doc')}]\n{d.get('content', '')}"
                            for d in result
                            if isinstance(d, dict)
                        )
                        tool_context_parts.append(f"## 관련 문서\n{docs_text}")
                        tool_results.append({"tool": "retriever", "query": query, "results": docs_text})

        if tool_context_parts:
            messages.append({
                "role": "system",
                "content": "\n\n".join(tool_context_parts) + "\n\n위 정보를 참고해서 답변하세요.",
            })

        # Generate response with metrics
        async with record_agent_metrics(
            self.metrics_store,
            session_id,
            self.name,
            self.llm.config.model,
            user_id,
        ) as metrics:
            response, usage = await self.llm.generate_with_usage(messages)
            metrics.set_token_count(usage.get("input_tokens", 0), usage.get("output_tokens", 0))

        # Store in short-term memory
        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        # Extract and save user facts
        if user_id and self.user_profiler:
            await self._extract_user_facts(user_id, current_messages)

        # Process topics for cross-session linking
        # Use full conversation history (messages includes history from memory)
        if self.topic_memory and user_id:
            await self._process_topics(session_id, messages)

        # Update workflow state for multi-step pipelines
        workflow_updates = self._update_workflow_state(state, response)

        return {
            **state,
            "messages": [
                *state["messages"],
                {"role": "assistant", "content": response},
            ],
            "tool_results": [*state.get("tool_results", []), *tool_results],
            **workflow_updates,
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
        """Disabled: LLM-based fact extraction was consuming 2 extra LLM calls per query."""

    async def _process_topics(self, session_id: str, messages: list[dict]) -> None:
        """Disabled: LLM-based topic extraction was consuming extra LLM calls every 5 messages."""
