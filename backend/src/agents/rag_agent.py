"""RAG agent for document-based Q&A."""

import unicodedata
from pathlib import Path
from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import DocumentRetriever, LLMProvider, MemoryStore
from src.graph.state import AgentState

logger = get_logger(__name__)


def _clean_source_name(metadata: dict, fallback: str) -> str:
    """Return a clean, human-readable source label.

    Prefers 'filename' over 'source' because 'source' can contain
    encoding-corrupted characters from some PDF uploads.
    Applies NFC normalization and strips the file extension.
    """
    raw = metadata.get("filename") or metadata.get("source") or fallback
    normalized = unicodedata.normalize("NFC", str(raw))
    return Path(normalized).stem  # remove .pdf / .docx etc.


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
- Do NOT make assumptions or fill in gaps with your own knowledge
- If the context doesn't contain relevant information, say "I couldn't find relevant information in the available documents."
- If you're uncertain, explicitly state uncertainty

Response format:
1. Answer the question using ONLY the provided context - write naturally without inline citations
2. At the very end, add a separator line (---) followed by referenced source documents:
   참고 문서: document name(s), comma-separated
3. Do NOT insert [Source: ...] tags inside the answer text

Formatting rules:
- Separate paragraphs with a blank line
- Always add a newline after headings (###)
- Always add a newline after URLs for readability
- Write list items on separate lines"""

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Retrieve relevant documents and generate answer."""
        session_id = state.get("metadata", {}).get("session_id", "default")
        device_id = state.get("metadata", {}).get("device_id")
        query = get_message_content(state["messages"][-1])

        # Retrieve relevant documents (filtered by session and device)
        try:
            docs = await self.retriever.retrieve(
                query, top_k=3, session_id=session_id, device_id=device_id
            )
        except Exception as e:
            logger.error("rag_retrieval_failed", error=str(e), session_id=session_id)
            docs = []

        if not docs:
            # No documents found - use LLM to generate natural fallback response
            # This ensures SSE tokens are streamed (not hardcoded silent response)
            messages = [{"role": "system", "content": self.system_prompt}]

            if self.memory:
                history = await self.memory.get_messages(session_id)
                messages.extend(history)

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Context: No relevant documents were found in the uploaded documents "
                        "for this session.\n\n"
                        "The user asked: " + query + "\n\n"
                        "Please inform the user in their language (Korean if the query is in Korean) that:\n"
                        "1. No relevant information was found in the uploaded documents\n"
                        "2. Suggest they try web search, upload relevant documents, or ask as a general question\n"
                        "Keep the response helpful and concise."
                    ),
                }
            )

            response = await self.llm.generate(messages)
            tool_results = [{"tool": "retriever", "query": query, "results": []}]
        else:
            # Check if all results are low confidence
            has_low_confidence = any(doc.get("low_confidence", False) for doc in docs)

            # Format context with confidence indicators
            context_parts = []
            source_names = []
            for i, doc in enumerate(docs, 1):
                source = _clean_source_name(doc.get("metadata", {}), f"Document {i}")
                content = doc.get("content", "")
                score = doc.get("score", 0)
                confidence_note = " [PARTIAL MATCH]" if doc.get("low_confidence") else ""
                source_names.append(source)
                context_parts.append(
                    f"[Document {i}: {source} | Relevance: {score:.2f}{confidence_note}]\n{content}"
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

            sources_list = ", ".join(dict.fromkeys(source_names))  # deduplicated
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Context:\n{context}{confidence_warning}\n\n"
                        f"Question: {query}\n\n"
                        f"[Referenced sources for footer: {sources_list}]"
                    ),
                }
            )

            response = await self.llm.generate(messages)
            tool_results = [{"tool": "retriever", "query": query, "results": docs}]

        # Note: Memory storage is handled by chat_agent to avoid duplication
        # RAG agent only adds response to state, not to memory

        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            "tool_results": [*state.get("tool_results", []), *tool_results],
        }
