"""Research evidence planning, execution, and formatting."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.graph.state import AgentState

logger = get_logger(__name__)

DOCUMENT_INTENT_TERMS = ("rag", "문서", "자료", "파일", "업로드", "pdf", "document")
SUMMARY_INTENT_TERMS = ("요약", "summary", "summarize")
WEB_INTENT_TERMS = (
    "최신",
    "현재",
    "지금",
    "오늘",
    "최근",
    "뉴스",
    "검색",
    "날씨",
    "주가",
    "price",
    "news",
)
REPORT_INTENT_TERMS = ("보고서", "리포트", "report", "종합")
SNIPPET_CHAR_LIMIT = 320


@dataclass(frozen=True)
class ResearchIntent:
    """Detected evidence intent for guardrail routing."""

    document: bool
    web: bool
    report: bool
    summary: bool


class ResearchToolDecision(BaseModel):
    """Tool plan chosen for a research turn."""

    tools: list[str] = Field(
        default_factory=list,
        description="Tools to use before answering. Allowed values: web_search, retriever.",
    )
    response_mode: Literal["answer", "report"] = Field(
        default="answer",
        description="Use report for synthesis/report requests, otherwise answer.",
    )
    reasoning: str = Field(default="", description="Brief reason for the tool choice.")


@dataclass(frozen=True)
class ResearchEvidence:
    """Collected evidence and formatted context for a research answer."""

    decision: ResearchToolDecision
    tool_results: list[dict]
    context: str
    confidence: str = "none"
    evidence_count: int = 0
    evidence_items: list[dict] = field(default_factory=list)
    warning: str | None = None


class ResearchEvidenceCollector:
    """Owns research tool decisions, execution, and evidence formatting."""

    def __init__(self, llm, search_tool=None, retriever=None) -> None:
        self.llm = llm
        self.search_tool = search_tool
        self.retriever = retriever

    async def collect(
        self,
        *,
        query: str,
        session_id: str,
        device_id: str | None,
        state: AgentState,
    ) -> ResearchEvidence:
        """Choose tools, execute them, and format collected context."""
        decision = await self.decide_tools(query, state)
        tool_results = await self.execute_tools(
            decision.tools,
            query,
            session_id,
            device_id,
            state,
        )
        normalized = self.normalize_tool_results(tool_results)
        evidence_items = self.collect_evidence_items(normalized)
        return ResearchEvidence(
            decision=decision,
            tool_results=normalized,
            context=self.format_tool_context(normalized),
            confidence=self.estimate_confidence(normalized),
            evidence_count=self.count_evidence(normalized),
            evidence_items=evidence_items,
            warning=self.build_evidence_warning(normalized),
        )

    async def decide_tools(self, query: str, state: AgentState) -> ResearchToolDecision:
        """Ask the LLM which research tools are needed."""
        available_tools = self.available_tools()
        intent = self.detect_intent(query)
        if not intent.document and not intent.web and not intent.report and not intent.summary:
            return ResearchToolDecision(
                tools=[],
                response_mode="answer",
                reasoning="No explicit research evidence intent detected.",
            )
        messages = [
            {
                "role": "system",
                "content": """You decide which tools a research agent should use.

Allowed tools:
- web_search: current or public web information.
- retriever: uploaded/RAG document information.

Rules:
- Use retriever for explicit RAG/document/file/uploaded-material questions.
- Use retriever for summarization requests when uploaded documents are available.
- Use web_search for latest/current/news/weather/stock/price/public web questions.
- Use both tools for synthesis/report requests that need current web and uploaded document context.
- Use no tools only when the answer can be produced without external evidence.
- response_mode must be report for 보고서/report/종합/synthesis requests, otherwise answer.""",
            },
            {
                "role": "user",
                "content": (
                    f"User query:\n{query}\n\n"
                    f"Available tools: {available_tools}\n"
                    f"has_documents: {state.get('has_documents', False)}"
                ),
            },
        ]

        try:
            data = await self.llm.generate_structured(messages, output_schema=ResearchToolDecision)
            if data:
                decision = self.sanitize_decision(data, available_tools)
                return self.enforce_explicit_tool_intent(
                    decision,
                    query,
                    available_tools,
                    has_documents=state.get("has_documents", False),
                )
        except Exception as e:
            logger.warning("research_tool_decision_failed", error=str(e))

        return self.fallback_decision(
            query,
            available_tools,
            has_documents=state.get("has_documents", False),
        )

    def available_tools(self) -> list[str]:
        """List tools configured for this research turn."""
        tools = []
        if self.search_tool:
            tools.append("web_search")
        if self.retriever:
            tools.append("retriever")
        return tools

    def sanitize_decision(self, data: dict, available_tools: list[str]) -> ResearchToolDecision:
        """Constrain LLM tool choices to configured tools."""
        tools = []
        for tool in data.get("tools", []):
            if tool in {"web_search", "retriever"} and tool in available_tools and tool not in tools:
                tools.append(tool)
        mode = data.get("response_mode", "answer")
        if mode not in {"answer", "report"}:
            mode = "answer"
        return ResearchToolDecision(
            tools=tools,
            response_mode=mode,
            reasoning=data.get("reasoning", ""),
        )

    def enforce_explicit_tool_intent(
        self,
        decision: ResearchToolDecision,
        query: str,
        available_tools: list[str],
        has_documents: bool = False,
    ) -> ResearchToolDecision:
        """Guard obvious tool requirements even if the LLM under-selects tools."""
        intent = self.detect_intent(query)
        tools = list(decision.tools)

        if "retriever" in available_tools and intent.document and "retriever" not in tools:
            tools.append("retriever")
        if (
            "retriever" in available_tools
            and intent.report
            and has_documents
            and "retriever" not in tools
        ):
            tools.append("retriever")
        if (
            "retriever" in available_tools
            and intent.summary
            and has_documents
            and "retriever" not in tools
        ):
            tools.append("retriever")
        if (
            "web_search" in available_tools
            and intent.web
            and (not intent.document or intent.report)
            and "web_search" not in tools
        ):
            tools.append("web_search")

        return ResearchToolDecision(
            tools=tools,
            response_mode=decision.response_mode,
            reasoning=decision.reasoning,
        )

    def detect_intent(self, query: str) -> ResearchIntent:
        """Return evidence intent flags for guardrail routing."""
        lowered = query.lower()
        return ResearchIntent(
            document=any(term in lowered for term in DOCUMENT_INTENT_TERMS),
            web=any(term in lowered for term in WEB_INTENT_TERMS),
            report=any(term in lowered for term in REPORT_INTENT_TERMS),
            summary=any(term in lowered for term in SUMMARY_INTENT_TERMS),
        )

    def fallback_decision(
        self,
        query: str,
        available_tools: list[str],
        has_documents: bool = False,
    ) -> ResearchToolDecision:
        """Deterministic fallback if structured tool choice fails."""
        tools = []
        intent = self.detect_intent(query)

        if "retriever" in available_tools and intent.document:
            tools.append("retriever")
        if (
            "retriever" in available_tools
            and intent.report
            and has_documents
            and "retriever" not in tools
        ):
            tools.append("retriever")
        if (
            "retriever" in available_tools
            and intent.summary
            and has_documents
            and "retriever" not in tools
        ):
            tools.append("retriever")
        if (
            "web_search" in available_tools
            and "web_search" not in tools
            and intent.web
            and (not intent.document or intent.report)
        ):
            tools.append("web_search")
        mode = "report" if intent.report else "answer"
        return ResearchToolDecision(
            tools=tools,
            response_mode=mode,
            reasoning="Structured tool routing failed; deterministic fallback used.",
        )

    async def execute_tools(
        self,
        tools: list[str],
        query: str,
        session_id: str,
        device_id: str | None,
        state: AgentState,
    ) -> list[dict]:
        """Execute selected tools concurrently where possible."""
        tasks = []
        if "web_search" in tools:
            tasks.append(("web_search", self.run_web_search(query)))
        if "retriever" in tools:
            tasks.append(("retriever", self.run_retriever(query, session_id, device_id, state)))

        if not tasks:
            return []

        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        tool_results = []
        for (tool_name, _), result in zip(tasks, results, strict=True):
            if isinstance(result, Exception):
                logger.warning("research_tool_failed", tool=tool_name, error=str(result))
                tool_results.append(
                    {"tool": tool_name, "query": query, "results": [], "error": str(result)}
                )
            else:
                tool_results.append(result)
        return tool_results

    async def run_web_search(self, query: str) -> dict:
        """Run the configured web search adapter."""
        if not self.search_tool:
            return {
                "tool": "web_search",
                "query": query,
                "results": "",
                "error": "web_search tool is not configured",
            }
        result = await self.search_tool.execute(query)
        return {"tool": "web_search", "query": query, "results": result}

    async def run_retriever(
        self,
        query: str,
        session_id: str,
        device_id: str | None,
        state: AgentState,
    ) -> dict:
        """Run the configured RAG document retriever adapter."""
        if not self.retriever:
            return {
                "tool": "retriever",
                "query": query,
                "results": [],
                "error": "retriever tool is not configured",
            }
        if not state.get("has_documents"):
            return {
                "tool": "retriever",
                "query": query,
                "results": [],
                "error": "no documents are available for this session",
            }
        docs = await self.retriever.execute(
            query,
            top_k=3,
            session_id=session_id,
            device_id=device_id,
        )
        return {"tool": "retriever", "query": query, "results": docs}

    def normalize_tool_results(self, tool_results: list[dict]) -> list[dict]:
        """Add common evidence metadata to tool results."""
        return [self.normalize_tool_result(result) for result in tool_results]

    def normalize_tool_result(self, result: dict) -> dict:
        """Normalize one tool result."""
        item = dict(result)
        if item.get("error"):
            item["evidence_count"] = 0
            item["confidence"] = "error"
            item["sources"] = []
            item["evidence_items"] = []
            return item

        tool = item.get("tool")
        if tool == "retriever":
            return self.normalize_retriever_result(item)
        if tool == "web_search":
            return self.normalize_web_search_result(item)

        item["evidence_count"] = 0
        item["confidence"] = "none"
        item["evidence_items"] = []
        return item

    def normalize_retriever_result(self, item: dict) -> dict:
        """Add evidence metadata for uploaded-document retrieval results."""
        docs = item.get("results") or []
        scores = [
            float(doc.get("score", 0))
            for doc in docs
            if isinstance(doc, dict) and doc.get("score") is not None
        ]
        evidence_items = [
            self.create_retriever_evidence_item(doc)
            for doc in docs
            if isinstance(doc, dict)
        ]
        item["evidence_items"] = evidence_items
        item["evidence_count"] = len(evidence_items)
        item["sources"] = self.extract_sources_from_evidence_items(evidence_items)
        item["confidence"] = self.score_confidence(max(scores) if scores else 0)
        return item

    def normalize_web_search_result(self, item: dict) -> dict:
        """Add evidence metadata for web search results."""
        text = str(item.get("results") or "")
        evidence_items = self.create_web_evidence_items(text)
        item["evidence_items"] = evidence_items
        item["evidence_count"] = len(evidence_items)
        item["sources"] = self.extract_sources_from_evidence_items(evidence_items)
        item["confidence"] = "medium" if text.strip() else "none"
        return item

    def score_confidence(self, score: float) -> str:
        """Map retriever score to a coarse confidence level."""
        if score >= 0.8:
            return "high"
        if score >= 0.5:
            return "medium"
        if score > 0:
            return "low"
        return "none"

    def create_retriever_evidence_item(self, doc: dict) -> dict:
        """Build a bounded, UI-safe evidence item from a retriever result."""
        metadata = doc.get("metadata") or {}
        score = self.safe_float(doc.get("score"))
        heading_path = metadata.get("heading_path_text") or self.heading_path_text(
            metadata.get("heading_path", [])
        )
        source = str(metadata.get("source") or metadata.get("filename") or "uploaded document")
        snippet_source = doc.get("matched_excerpt") or doc.get("content") or ""
        return {
            "tool": "retriever",
            "source": source,
            "page": self.safe_int(metadata.get("page")),
            "page_end": self.safe_int(metadata.get("page_end")),
            "heading_path": heading_path,
            "score": score,
            "confidence": self.score_confidence(score),
            "snippet": self.truncate_snippet(snippet_source),
        }

    def create_web_evidence_items(self, text: str) -> list[dict]:
        """Build evidence items from markdown-style web search links."""
        if not text.strip():
            return []

        items = []
        seen_urls: set[str] = set()
        for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
            title = match.group(1).strip()
            url = match.group(2).strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            items.append(
                {
                    "tool": "web_search",
                    "source": url,
                    "url": url,
                    "title": title,
                    "page": None,
                    "page_end": None,
                    "heading_path": "",
                    "score": None,
                    "confidence": "medium",
                    "snippet": self.truncate_snippet(text),
                }
            )

        if items:
            return items

        return [
            {
                "tool": "web_search",
                "source": "web_search",
                "url": None,
                "title": "",
                "page": None,
                "page_end": None,
                "heading_path": "",
                "score": None,
                "confidence": "medium",
                "snippet": self.truncate_snippet(text),
            }
        ]

    def truncate_snippet(self, content: object, limit: int = SNIPPET_CHAR_LIMIT) -> str:
        """Normalize and bound evidence snippets before they leave the backend."""
        text = str(content or "").strip()
        if not text:
            return ""

        lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        ]
        normalized = "\n".join(line for line in lines if line)
        if len(normalized) <= limit:
            return normalized
        return normalized[: max(limit - 3, 0)].rstrip() + "..."

    def heading_path_text(self, heading_path: object) -> str:
        """Normalize heading path metadata into a display string."""
        if isinstance(heading_path, list):
            return " > ".join(str(part) for part in heading_path if part)
        if heading_path:
            return str(heading_path)
        return ""

    def safe_float(self, value: object) -> float:
        """Return a JSON-safe float score."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def safe_int(self, value: object) -> int | None:
        """Return an int metadata value when available."""
        try:
            if value is None or value == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def collect_evidence_items(self, tool_results: list[dict]) -> list[dict]:
        """Flatten normalized tool evidence into a common contract."""
        items = []
        for result in tool_results:
            for item in result.get("evidence_items", []):
                if isinstance(item, dict):
                    items.append(item)
        return items

    def extract_sources_from_evidence_items(self, evidence_items: list[dict]) -> list[str]:
        """Extract displayable unique sources from normalized evidence items."""
        sources = []
        for item in evidence_items:
            source = item.get("source")
            if source and source not in sources:
                sources.append(str(source))
        return sources

    def extract_document_sources(self, docs: list[dict]) -> list[str]:
        """Extract displayable document sources from retrieved chunks."""
        sources = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            metadata = doc.get("metadata", {})
            source = metadata.get("source") or metadata.get("filename")
            if source and source not in sources:
                sources.append(str(source))
        return sources

    def extract_markdown_links(self, text: str) -> list[str]:
        """Extract markdown URLs from formatted web search output."""
        urls = []
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
            url = match.group(1)
            if url not in urls:
                urls.append(url)
        return urls

    def build_evidence_warning(self, tool_results: list[dict]) -> str | None:
        """Return abstention guidance for missing or weak required evidence."""
        warnings = []
        for result in tool_results:
            tool = result.get("tool")
            evidence_count = int(result.get("evidence_count", 0))
            confidence = result.get("confidence", "none")
            error = result.get("error")

            if tool == "retriever":
                if error:
                    warnings.append(
                        "Uploaded-document evidence is unavailable. Do not answer document-specific "
                        "questions from general knowledge; state that document evidence could not be checked."
                    )
                elif evidence_count == 0:
                    warnings.append(
                        "No matching uploaded-document evidence was found. For document or RAG questions, "
                        "state that the uploaded documents do not provide enough evidence."
                    )
                elif confidence == "low":
                    warnings.append(
                        "Uploaded-document evidence is low confidence. Do not present unsupported specifics; "
                        "state the limitation clearly."
                    )

            if tool == "web_search":
                if error:
                    warnings.append(
                        "Web evidence is unavailable. For current or news questions, state that current "
                        "information could not be verified."
                    )
                elif evidence_count == 0:
                    warnings.append(
                        "No web evidence was found. For current or news questions, avoid unsupported claims."
                    )

        return " ".join(warnings) if warnings else None

    def count_evidence(self, tool_results: list[dict]) -> int:
        """Count evidence items across normalized tool results."""
        return sum(int(result.get("evidence_count", 0)) for result in tool_results)

    def estimate_confidence(self, tool_results: list[dict]) -> str:
        """Estimate overall evidence confidence."""
        levels = [result.get("confidence", "none") for result in tool_results]
        if "high" in levels:
            return "high"
        if "medium" in levels:
            return "medium"
        if "low" in levels:
            return "low"
        if "error" in levels:
            return "error"
        return "none"

    def format_tool_context(self, tool_results: list[dict]) -> str:
        """Format tool outputs for the final LLM call."""
        parts = []
        for result in tool_results:
            tool = result.get("tool")
            if result.get("error"):
                parts.append(f"[{tool} error]\n{result['error']}")
                continue
            if tool == "web_search":
                sources = ", ".join(result.get("sources", [])) or "No parsed sources"
                parts.append(
                    f"[web_search | confidence={result.get('confidence', 'none')} | sources={sources}]\n"
                    f"{result.get('results', '')}"
                )
            elif tool == "retriever":
                docs = result.get("results", [])
                sources = ", ".join(result.get("sources", [])) or "No sources"
                parts.append(
                    f"[retriever | confidence={result.get('confidence', 'none')} | sources={sources}]\n"
                    + self.format_docs(docs)
                )
        return "\n\n---\n\n".join(part for part in parts if part.strip())

    def format_docs(self, docs: list[dict]) -> str:
        """Format retrieved document chunks."""
        if not docs:
            return "No matching uploaded document chunks were found."
        return "\n\n".join(
            f"[{doc.get('metadata', {}).get('source') or doc.get('metadata', {}).get('filename') or 'doc'}]\n"
            f"{doc.get('content', '')}"
            for doc in docs
            if isinstance(doc, dict)
        )
