"""Code agent for programming tasks."""

import re
from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore, Tool
from src.graph.state import AgentState

logger = get_logger(__name__)


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
        llm: LLMProvider = Provide[DIContainer.llm],
        code_executor: Tool | None = None,
        memory: MemoryStore = Provide[DIContainer.memory],
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
- ALWAYS execute the code you write and show the output clearly
- NEVER say you cannot execute code - you have code_executor tool available

When writing code:
1. First understand the requirements
2. Write the code with proper structure
3. Add comments for clarity
4. ALWAYS include example calls after defining functions or classes:
   - Add print() calls with representative inputs so execution produces visible output
   - Bad:  def fibonacci(n): ...
   - Good: def fibonacci(n): ...
           print(fibonacci(0))   # 0
           print(fibonacci(10))  # 55
5. Write the code only - DO NOT include execution results in your response
   - The system will automatically execute your code and display results separately
   - Including results in your response causes duplicate output
6. Test edge cases mentally

Formatting Rules (IMPORTANT):
- ALWAYS use proper markdown formatting
- When citing URLs or references, use proper format: [text](https://example.com)
- ALWAYS separate URLs from surrounding text with proper spacing
- NEVER include spaces inside URLs: use https://example.com NOT https://example. com"""

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

        # Extract and execute Python code blocks if code executor is available
        if self.code_executor:
            code_blocks = self._extract_python_code(response)
            for i, code in enumerate(code_blocks, 1):
                result = await self.code_executor.execute(code)
                tool_results.append({
                    "tool": "code_executor",
                    "block_number": i,
                    "result": result,
                })
                # Append execution result to response
                exec_output = self._format_execution_result(result, i)
                response = response + exec_output

        # Store the code exchange in memory if available
        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        # Update workflow state for multi-step pipelines
        workflow_updates = self._update_workflow_state(state, response)

        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            "tool_results": [*state.get("tool_results", []), *tool_results],
            **workflow_updates,
        }

    def _extract_python_code(self, text: str) -> list[str]:
        """Extract Python code blocks from markdown text.

        Args:
            text: The response text containing code blocks

        Returns:
            List of extracted Python code strings
        """
        # Match ```python ... ``` blocks (allow optional trailing whitespace after language tag)
        python_pattern = r"```python[ \t]*\n(.*?)\n```"
        matches = re.findall(python_pattern, text, re.DOTALL)

        # Also match ```py ... ``` blocks
        py_pattern = r"```py[ \t]*\n(.*?)\n```"
        matches.extend(re.findall(py_pattern, text, re.DOTALL))

        # Clean up and return non-empty blocks
        code_blocks = []
        for match in matches:
            code = match.strip()
            if code and not code.startswith("#"):  # Skip empty or comment-only blocks
                code_blocks.append(code)

        return code_blocks

    def _format_execution_result(self, result: dict, block_number: int) -> str:
        """Format code execution result for display.

        Args:
            result: The execution result dict with success, stdout, stderr
            block_number: The code block number for reference

        Returns:
            Formatted result string to append to response
        """
        output = [f"\n\n---\n**코드 실행 결과 #{block_number}:**"]

        if result.get("success"):
            output.append("✅ 실행 성공")
        else:
            output.append("❌ 실행 실패")

        stdout = result.get("stdout", "").strip()
        if stdout:
            output.append(f"\n**출력:**\n```\n{stdout}\n```")

        stderr = result.get("stderr", "").strip()
        if stderr:
            output.append(f"\n**오류:**\n```\n{stderr}\n```")

        if not stdout and not stderr:
            output.append("\n(출력 없음)")

        return "\n".join(output)
