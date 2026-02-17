"""RAG agent for document-based Q&A."""

from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.protocols import DocumentRetriever, LLMProvider, MemoryStore
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


class RAGAgent(BaseAgent):
    """Retrieval-Augmented Generation agent for document-based Q&A."""

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "rag"

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        retriever: DocumentRetriever = Provide[DIContainer.retriever],
        memory: MemoryStore = Provide[DIContainer.memory],
    ):
        super().__init__(llm, memory=memory)
        self.retriever = retriever

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        return """You are an expert at answering questions based on provided document context.

Guidelines:
- ONLY use information from the provided context to answer questions
- If the context doesn't contain relevant information, say "I couldn't find relevant information in the available documents."
- Always cite your sources by mentioning which document/section the information came from
- Be precise and accurate
- If multiple sources provide different information, present all perspectives"""

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Retrieve relevant documents and generate answer."""
        session_id = state.get("metadata", {}).get("session_id", "default")
        query = get_message_content(state["messages"][-1])

        # Retrieve relevant documents (filtered by session)
        try:
            docs = await self.retriever.retrieve(query, top_k=3, session_id=session_id)
        except Exception:
            docs = []

        if not docs:
            response = "I couldn't find any relevant documents to answer your question. Please make sure documents have been uploaded to the knowledge base."
            tool_results = [{"tool": "retriever", "query": query, "results": []}]
        else:
            # Format context
            context_parts = []
            for i, doc in enumerate(docs, 1):
                source = doc.get("metadata", {}).get("source", f"Document {i}")
                content = doc.get("content", "")
                context_parts.append(f"[Source: {source}]\n{content}")

            context = "\n\n---\n\n".join(context_parts)

            # Build messages with conversation history if memory is available
            messages = [{"role": "system", "content": self.system_prompt}]

            if self.memory:
                history = await self.memory.get_messages(session_id)
                messages.extend(history)

            messages.append(
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {query}",
                }
            )

            response = await self.llm.generate(messages)
            tool_results = [{"tool": "retriever", "query": query, "results": docs}]

        # Store the Q&A exchange in memory if available
        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            "tool_results": [*state.get("tool_results", []), *tool_results],
        }
