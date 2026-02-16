"""Code agent for programming tasks."""

from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.container import Container
from src.core.protocols import LLMProvider, MemoryStore, Tool
from src.graph.state import AgentState


def message_to_dict(msg) -> dict:
    """Convert LangChain message to dict format."""
    if isinstance(msg, dict):
        return msg
    if isinstance(msg, BaseMessage):
        return {"role": msg.type, "content": msg.content}
    return {"role": "user", "content": str(msg)}


class CodeAgent(BaseAgent):
    """Agent for code generation, analysis, and debugging."""

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "code"

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[Container.llm],
        code_executor: Tool | None = None,
        memory: MemoryStore = Provide[Container.memory],
    ):
        super().__init__(llm, memory=memory)
        self.code_executor = code_executor

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        return """You are an expert programmer and code assistant.

Guidelines:
- Write clean, well-documented code
- Include helpful comments explaining complex logic
- Follow best practices and idiomatic patterns for the language
- When debugging, explain the issue and the fix
- Suggest improvements when reviewing code
- Be security-conscious and warn about potential vulnerabilities
- If executing code, show the output clearly

When writing code:
1. First understand the requirements
2. Write the code with proper structure
3. Add comments for clarity
4. Test edge cases mentally
5. Explain how the code works"""

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Generate code and optionally execute it."""
        session_id = state.get("metadata", {}).get("session_id", "default")

        messages = [{"role": "system", "content": self.system_prompt}]

        # Include conversation history if memory is available
        if self.memory:
            history = await self.memory.get_messages(session_id)
            messages.extend(history)

        # Convert LangChain messages to dict format
        for msg in state["messages"]:
            messages.append(message_to_dict(msg))

        response = await self.llm.generate(messages)

        tool_results = []

        # If code executor is available and the response contains Python code,
        # we could optionally execute it here (commented out for safety)
        # if self.code_executor and "```python" in response:
        #     # Extract and execute code
        #     pass

        # Store the code exchange in memory if available
        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            "tool_results": [*state.get("tool_results", []), *tool_results],
        }
