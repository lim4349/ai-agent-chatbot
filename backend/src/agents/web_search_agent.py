"""Web search agent for real-time information."""

from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.protocols import LLMProvider, MemoryStore, Tool
from src.graph.state import AgentState


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
- Always cite sources with their URLs
- Present information in a clear, organized manner
- If sources conflict, present multiple perspectives
- Focus on the most relevant and recent information
- Be honest about the limitations of search results

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
  Wrong:  "- 136.31달러 (출처: https://www.example.com/order- 142.91달러"
  Right:  "- 136.31달러 (출처: https://www.example.com/order)\n- 142.91달러"""

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
                    "content": f"Search Results:\n{search_results}\n\nQuestion: {query}",
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
