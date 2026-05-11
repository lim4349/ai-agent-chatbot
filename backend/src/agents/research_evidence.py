"""Research evidence planning, execution, and formatting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.graph.state import AgentState

logger = get_logger(__name__)


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
        return ResearchEvidence(
            decision=decision,
            tool_results=tool_results,
            context=self.format_tool_context(tool_results),
        )

    async def decide_tools(self, query: str, state: AgentState) -> ResearchToolDecision:
        """Ask the LLM which research tools are needed."""
        available_tools = self.available_tools()
        messages = [
            {
                "role": "system",
                "content": """You decide which tools a research agent should use.

Allowed tools:
- web_search: current or public web information.
- retriever: uploaded/RAG document information.

Rules:
- Use retriever for explicit RAG/document/file/uploaded-material questions.
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
        document_requested, web_requested, report_requested = self.intent_flags(query)
        tools = list(decision.tools)

        if "retriever" in available_tools and document_requested and "retriever" not in tools:
            tools.append("retriever")
        if (
            "retriever" in available_tools
            and report_requested
            and has_documents
            and "retriever" not in tools
        ):
            tools.append("retriever")
        if (
            "web_search" in available_tools
            and web_requested
            and (not document_requested or report_requested)
            and "web_search" not in tools
        ):
            tools.append("web_search")

        return ResearchToolDecision(
            tools=tools,
            response_mode=decision.response_mode,
            reasoning=decision.reasoning,
        )

    def intent_flags(self, query: str) -> tuple[bool, bool, bool]:
        """Return document, web, and report intent flags for guardrail routing."""
        lowered = query.lower()
        document_requested = any(
            term in lowered for term in ("rag", "문서", "자료", "파일", "업로드", "pdf", "document")
        )
        web_requested = any(
            term in lowered
            for term in (
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
        )
        report_requested = any(term in lowered for term in ("보고서", "리포트", "report", "종합"))
        return document_requested, web_requested, report_requested

    def fallback_decision(
        self,
        query: str,
        available_tools: list[str],
        has_documents: bool = False,
    ) -> ResearchToolDecision:
        """Deterministic fallback if structured tool choice fails."""
        tools = []
        document_requested, web_requested, report_requested = self.intent_flags(query)

        if "retriever" in available_tools and document_requested:
            tools.append("retriever")
        if (
            "retriever" in available_tools
            and report_requested
            and has_documents
            and "retriever" not in tools
        ):
            tools.append("retriever")
        if (
            "web_search" in available_tools
            and "web_search" not in tools
            and web_requested
            and (not document_requested or report_requested)
        ):
            tools.append("web_search")
        mode = "report" if report_requested else "answer"
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

    def format_tool_context(self, tool_results: list[dict]) -> str:
        """Format tool outputs for the final LLM call."""
        parts = []
        for result in tool_results:
            tool = result.get("tool")
            if result.get("error"):
                parts.append(f"[{tool} error]\n{result['error']}")
                continue
            if tool == "web_search":
                parts.append(f"[web_search]\n{result.get('results', '')}")
            elif tool == "retriever":
                docs = result.get("results", [])
                parts.append("[retriever]\n" + self.format_docs(docs))
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
