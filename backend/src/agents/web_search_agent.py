"""Web search agent for real-time information."""

from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore, Tool
from src.graph.state import AgentState

logger = get_logger(__name__)


def get_message_content(msg) -> str:
    """Extract content from a message (dict or LangChain message)."""
    if isinstance(msg, dict):
        return msg.get("content", "")
    if isinstance(msg, BaseMessage):
        return msg.content
    return str(msg)


def message_to_dict(msg) -> dict:
    """Convert LangChain message to dict format."""
    if isinstance(msg, dict):
        return msg
    if isinstance(msg, BaseMessage):
        return {"role": msg.type, "content": msg.content}
    return {"role": "user", "content": str(msg)}


class WebSearchAgent(BaseAgent):
    """Agent for searching the web for current information."""

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "web_search"

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        search_tool: Tool = Provide[DIContainer.tool_registry],
        memory: MemoryStore = Provide[DIContainer.memory],
    ):
        super().__init__(llm, tools=[search_tool], memory=memory)
        self.search_tool = search_tool

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        return """You are an expert at synthesizing web search results into clear, informative answers.

Guidelines:
- Synthesize information from multiple sources when available
- Present information in a clear, organized manner
- If sources conflict, present multiple perspectives
- Focus on the most relevant and recent information
- Be honest about the limitations of search results

Formatting Rules (CRITICAL - MUST FOLLOW):
- Use proper line breaks between list items
- Start each list item on its own line with "- " or a number
- Add a blank line between the main text and list items
- Ensure proper spacing after periods

Examples:
❌ WRONG:
주가는 다음과 같습니다- 136.31달러- 142.91달러

✅ CORRECT:
주가는 다음과 같습니다

- 136.31달러
- 142.91달러"""

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Search the web and generate response."""
        session_id = state.get("metadata", {}).get("session_id", "default")
        query = get_message_content(state["messages"][-1])

        tool_results = []

        try:
            search_results = await self.search_tool.execute(query=query)
            tool_results.append({"tool": "web_search", "query": query, "results": search_results})

            # Build messages with conversation history if memory is available
            messages = [{"role": "system", "content": self.system_prompt}]

            if self.memory:
                history = await self.memory.get_messages(session_id)
                messages.extend(history)

            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Search Results:\n{search_results}\n\n"
                        f"Question: {query}\n\n"
                        "CRITICAL FORMATTING INSTRUCTIONS:\n"
                        "1. DO NOT include source URLs in your response\n"
                        "2. DO NOT use '(출처: ...)' citations\n"
                        "3. Start each list item on its own line with '- ' or a number\n"
                        "4. Add proper line breaks between list items\n"
                        "5. Ensure spacing after periods (e.g., '입니다. 다음' not '입니다.다음')"
                    ),
                }
            )
            response = await self.llm.generate(messages)
        except Exception as e:
            response = f"I encountered an error while searching: {str(e)}. Please try again later."
            tool_results.append({"tool": "web_search", "query": query, "error": str(e)})

        # Store the search exchange in memory if available
        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            "tool_results": [*state.get("tool_results", []), *tool_results],
        }
