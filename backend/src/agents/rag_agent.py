"""RAG agent for document-based Q&A with structured output."""

import unicodedata
from pathlib import Path
from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import DocumentRetriever, LLMProvider, MemoryStore
from src.graph.state import AgentState

logger = get_logger(__name__)


class RAGParagraph(BaseModel):
    """A paragraph/section of the RAG response."""

    title: str | None = Field(
        default=None, description="Optional title/subject for this paragraph"
    )
    content: str = Field(
        description="Main text content. Each sentence should be complete and properly spaced."
    )
    bullet_points: list[str] = Field(
        default_factory=list,
        description="Optional bullet points under this paragraph. Each item is a complete sentence."
    )


class RAGResponse(BaseModel):
    """Structured response format for RAG queries."""

    paragraphs: list[RAGParagraph] = Field(
        description="List of paragraphs/sections that answer the question. Each paragraph has optional title, content text, and bullet points."
    )
    references: list[str] = Field(
        default_factory=list,
        description="List of source document names referenced in the answer"
    )
    confidence: str = Field(
        default="high",
        description="Confidence level: 'high' if documents clearly answer the question, 'medium' if partially, 'low' if unclear"
    )


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
- If the context doesn't contain relevant information, indicate low confidence
- If you're uncertain, explicitly state uncertainty

OUTPUT FORMAT INSTRUCTIONS:
You must output a structured JSON response with the following fields:
- paragraphs: Array of paragraph objects, each with:
  - title: Optional subtitle for this section (e.g., "주요 내용", "지원 대상")
  - content: Main text as complete sentences with proper spacing between sentences
  - bullet_points: Array of bullet point strings (optional, for lists)
- references: Array of source document names
- confidence: "high", "medium", or "low" based on how well documents answer the question

TEXT FORMATTING RULES:
1. Each sentence must end with proper punctuation and be separated by a space
2. Use paragraphs array to organize content by topic
3. Use bullet_points for list items (each should be a complete sentence)
4. References should be document filenames without extensions

Example output structure:
{
  "paragraphs": [
    {
      "title": "개요",
      "content": "IP나래는 중소기업 및 창업 기업을 위한 지식재산 관련 지원 프로그램입니다.",
      "bullet_points": []
    },
    {
      "title": "주요 내용",
      "content": "이 프로그램은 창업 후 7년 이내의 기업을 대상으로 합니다.",
      "bullet_points": [
        "목적: 기업의 기술이 독점 배타권을 가질 수 있도록 지원합니다.",
        "대상: 창업 후 7년 이내의 중소기업 및 전환창업 후 5년 이내의 기업입니다."
      ]
    }
  ],
  "references": ["2025_IP나래_인포플라_VLAgent_8회"],
  "confidence": "high"
}"""

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
                        f"Available source documents: {sources_list}\n\n"
                        f"Respond using the structured JSON format described in your instructions."
                    ),
                }
            )

            # Use structured output for consistent formatting
            structured_response = await self.llm.generate_structured(
                messages, output_schema=RAGResponse
            )

            if structured_response:
                # Convert structured response to formatted text
                response = self._format_structured_response(structured_response)
            else:
                # Fallback to regular generation if structured output fails
                response = await self.llm.generate(messages)

            tool_results = [{"tool": "retriever", "query": query, "results": docs}]

        # Note: Memory storage is handled by chat_agent to avoid duplication
        # RAG agent only adds response to state, not to memory

        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            "tool_results": [*state.get("tool_results", []), *tool_results],
        }

    def _format_structured_response(self, data: dict) -> str:
        """Convert structured RAGResponse to formatted text."""
        paragraphs = data.get("paragraphs", [])
        references = data.get("references", [])
        confidence = data.get("confidence", "high")

        parts = []

        for para in paragraphs:
            # Add title if present
            if title := para.get("title"):
                parts.append(f"\n{title}")

            # Add main content
            if content := para.get("content", "").strip():
                parts.append(content)

            # Add bullet points
            for bullet in para.get("bullet_points", []):
                parts.append(f"- {bullet}")

            parts.append("")  # Empty line between paragraphs

        # Add references section
        if references:
            parts.append("---")
            parts.append("")
            parts.append(f"참고 문서: {', '.join(references)}")

        # Add confidence note if low
        if confidence in ["low", "medium"]:
            parts.append("")
            parts.append(f"[신뢰도: {confidence}]")

        return "\n".join(parts)
