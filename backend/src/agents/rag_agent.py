"""RAG agent for document-based Q&A."""

from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import DocumentRetriever, LLMProvider, MemoryStore
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

CRITICAL RULES TO PREVENT HALLUCINATION:
- ONLY use information from the provided context - NEVER use outside knowledge
- You MUST cite sources using [Source: filename] format for EVERY claim you make
- If the context doesn't contain relevant information, say "I couldn't find relevant information in the available documents."
- Do NOT make assumptions or fill in gaps with your own knowledge
- If you're uncertain, explicitly state "Based on the available context, I'm not entirely certain, but..."

Response format:
1. Answer the question using ONLY the provided context
2. Include [Source: filename] citations for each claim
3. If multiple sources provide different information, present all perspectives
4. End with a brief note if information is incomplete or uncertain"""

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Retrieve relevant documents and generate answer."""
        session_id = state.get("metadata", {}).get("session_id", "default")
        query = get_message_content(state["messages"][-1])

        # Retrieve relevant documents (filtered by session)
        try:
            docs = await self.retriever.retrieve(query, top_k=3, session_id=session_id)
        except Exception as e:
            logger.error("rag_retrieval_failed", error=str(e), session_id=session_id)
            docs = []

        if not docs:
            # No documents found - provide helpful fallback response
            response = (
                "업로드된 문서에서 관련 정보를 찾을 수 없습니다.\n\n"
                "다음 방법을 시도해보세요:\n"
                '1. **웹 검색**: "웹에서 검색해줘"라고 요청하면 인터넷에서 찾아드릴 수 있습니다.\n'
                "2. **문서 업로드**: 관련 문서를 업로드하면 더 정확한 답변을 드릴 수 있습니다.\n"
                "3. **일반 대화**: 궁금한 점을 일반적인 질문으로 다시 물어보세요."
            )
            tool_results = [{"tool": "retriever", "query": query, "results": []}]
        else:
            # Check if all results are low confidence
            has_low_confidence = any(doc.get("low_confidence", False) for doc in docs)

            # Format context with confidence indicators
            context_parts = []
            for i, doc in enumerate(docs, 1):
                source = doc.get("metadata", {}).get("source", f"Document {i}")
                content = doc.get("content", "")
                score = doc.get("score", 0)
                confidence_note = " [PARTIAL MATCH]" if doc.get("low_confidence") else ""
                context_parts.append(
                    f"[Source: {source} | Relevance: {score:.2f}{confidence_note}]\n{content}"
                )

            context = "\n\n---\n\n".join(context_parts)

            # Add warning if results are low confidence
            confidence_warning = ""
            if has_low_confidence:
                confidence_warning = "\n\nWARNING: The retrieved documents have moderate relevance scores. Please be extra careful and explicitly mention uncertainty in your response."

            # Build messages with conversation history if memory is available
            messages = [{"role": "system", "content": self.system_prompt}]

            if self.memory:
                history = await self.memory.get_messages(session_id)
                messages.extend(history)

            messages.append(
                {
                    "role": "user",
                    "content": f"Context:\n{context}{confidence_warning}\n\nQuestion: {query}",
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
