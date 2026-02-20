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

## 참고 문서 섹션
- 본문과 참고 문서 사이에 --- 구분선 추가
- 구분선 앞뒤로 빈 줄 추가
- "참고 문서:" 뒤에 쉼표로 문서명 구분

완전한 응답 예시:
```
임성근은 한국의 유명한 셰프입니다.

흑백요리사:
- 독특한 요리 스타일로 인기를 얻고 있습니다
- 여러 요리 관련 프로그램에 출연하고 있습니다

경력:
- 칠레 산티아고 세계조리사총연맹 연회주 총괄 주방장
- 중국 베이징 주중대사관 국빈급 만찬 메인 총괄 셰프

---

참고 문서: 임성근_프로필.pdf, 흑백요리사_소개.pdf
```
"""

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
