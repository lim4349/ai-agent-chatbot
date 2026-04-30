"""Code agent for programming tasks."""

import re
from typing import override

from dependency_injector.wiring import Provide, inject

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore, Tool
from src.graph.state import AgentState
from src.observability import record_agent_metrics
from src.utils.message_utils import message_to_dict

logger = get_logger(__name__)


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
        metrics_store=Provide[DIContainer.metrics_store],
    ):
        super().__init__(llm, memory=memory)
        self.code_executor = code_executor
        self.metrics_store = metrics_store

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        execution_guidance = (
            """- When you write Python code, the system can execute fenced python code blocks.
- Include representative print() calls when execution would help verify the answer.
- Do not invent execution output; the system will append actual execution results."""
            if self.code_executor
            else """- Code execution is disabled in this environment.
- Provide code, explanation, and manual reasoning when useful.
- Do not claim that code was executed."""
        )

        return f"""You are an expert programmer and code assistant.

Guidelines:
- Write clean, well-documented code
- Include helpful comments explaining complex logic
- Follow best practices and idiomatic patterns for the language
- When debugging, explain the issue and the fix
- Suggest improvements when reviewing code
- Be security-conscious and warn about potential vulnerabilities
{execution_guidance}

When writing code:
1. First understand the requirements
2. Write the code with proper structure
3. Add comments for clarity
4. Include example calls after defining functions or classes when useful:
   - Add print() calls with representative inputs so execution produces visible output
   - Bad:  def fibonacci(n): ...
   - Good: def fibonacci(n): ...
           print(fibonacci(0))   # 0
           print(fibonacci(10))  # 55
5. If execution is enabled, write code only and let the system append actual results
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
        user_id = state.get("metadata", {}).get("user_id")

        messages = [{"role": "system", "content": self.system_prompt}]

        # Include conversation history if memory is available
        if self.memory:
            history = await self.memory.get_messages(session_id)
            messages.extend(history)

        # Convert LangChain messages to dict format
        for msg in state["messages"]:
            messages.append(message_to_dict(msg))

        tool_results = []
        response = ""

        async with record_agent_metrics(
            self.metrics_store,
            session_id,
            self.name,
            self.llm.config.model,
            user_id,
        ) as metrics:
            response, usage = await self.llm.generate_with_usage(messages)
            metrics.set_token_count(usage.get("input_tokens", 0), usage.get("output_tokens", 0))

            # Extract and execute Python code blocks if code executor is available
            if self.code_executor:
                code_blocks = self._extract_python_code(response)
                for i, code in enumerate(code_blocks, 1):
                    result = await self.code_executor.execute(code)
                    tool_results.append(
                        {
                            "tool": "code_executor",
                            "block_number": i,
                            "result": result,
                        }
                    )
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
            if not code:
                continue
            # Skip comment-only blocks (all lines are comments or blank)
            lines = code.split("\n")
            if all(line.strip().startswith("#") or not line.strip() for line in lines):
                continue
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
