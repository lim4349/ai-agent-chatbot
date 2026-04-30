"""Research agent with agentic web and document tool use."""

import asyncio
from typing import Literal, override

from dependency_injector.wiring import Provide, inject
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore
from src.graph.state import AgentState
from src.observability import record_agent_metrics
from src.utils.message_utils import get_message_content, message_to_dict

logger = get_logger(__name__)


class ResearchToolDecision(BaseModel):
    """Tool plan chosen by ResearchAgent."""

    tools: list[str] = Field(
        default_factory=list,
        description="Tools to use before answering. Allowed values: web_search, retriever.",
    )
    response_mode: Literal["answer", "report"] = Field(
        default="answer",
        description="Use report for synthesis/report requests, otherwise answer.",
    )
    reasoning: str = Field(default="", description="Brief reason for the tool choice.")


class ResearchAgent(BaseAgent):
    """Agent for RAG, web search, and research/report synthesis."""

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "research"

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        memory: MemoryStore = Provide[DIContainer.memory],
        search_tool=None,
        retriever=None,
        metrics_store=Provide[DIContainer.metrics_store],
    ):
        super().__init__(llm, memory=memory)
        self.search_tool = search_tool
        self.retriever = retriever
        self.metrics_store = metrics_store

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for final research answers."""
        return """You are a research agent.

You answer using collected evidence from web search and uploaded documents.

Guidelines:
- Use uploaded-document context when the user asks about RAG, documents, files, or uploaded material.
- Use web context for current, latest, market, weather, news, or public web questions.
- If requested evidence is unavailable, say so clearly instead of inventing details.
- For report requests, produce a concise structured report with headings.
- Respond in the user's language."""

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Choose tools, execute them, and generate a final research answer."""
        session_id = state.get("metadata", {}).get("session_id", "default")
        user_id = state.get("metadata", {}).get("user_id")
        device_id = state.get("metadata", {}).get("device_id") or user_id
        query = get_message_content(state["messages"][-1])

        decision = await self._decide_tools(query, state)
        tool_results = await self._execute_tools(decision.tools, query, session_id, device_id, state)
        tool_context = self._format_tool_context(tool_results)

        messages = [{"role": "system", "content": self.system_prompt}]
        if self.memory:
            history = await self.memory.get_messages(session_id)
            messages.extend(history)

        messages.extend(message_to_dict(msg) for msg in state["messages"])
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Tool plan: {decision.reasoning or 'No additional reasoning.'}\n"
                    f"Response mode: {decision.response_mode}\n\n"
                    f"Collected context:\n{tool_context or 'No tool context was collected.'}"
                ),
            }
        )

        async with record_agent_metrics(
            self.metrics_store,
            session_id,
            self.name,
            self.llm.config.model,
            user_id,
        ) as metrics:
            response, usage = await self.llm.generate_with_usage(messages)
            metrics.set_token_count(usage.get("input_tokens", 0), usage.get("output_tokens", 0))

        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        workflow_updates = self._update_workflow_state(state, response)
        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            "tool_results": [*state.get("tool_results", []), *tool_results],
            **workflow_updates,
        }

    async def _decide_tools(self, query: str, state: AgentState) -> ResearchToolDecision:
        """Ask the LLM which research tools are needed."""
        available_tools = []
        if self.search_tool:
            available_tools.append("web_search")
        if self.retriever:
            available_tools.append("retriever")

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
                decision = self._sanitize_decision(data, available_tools)
                return self._enforce_explicit_tool_intent(
                    decision,
                    query,
                    available_tools,
                    has_documents=state.get("has_documents", False),
                )
        except Exception as e:
            logger.warning("research_tool_decision_failed", error=str(e))

        return self._fallback_decision(
            query,
            available_tools,
            has_documents=state.get("has_documents", False),
        )

    def _sanitize_decision(self, data: dict, available_tools: list[str]) -> ResearchToolDecision:
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

    def _enforce_explicit_tool_intent(
        self,
        decision: ResearchToolDecision,
        query: str,
        available_tools: list[str],
        has_documents: bool = False,
    ) -> ResearchToolDecision:
        """Guard obvious tool requirements even if the LLM under-selects tools."""
        document_requested, web_requested, report_requested = self._intent_flags(query)
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

    def _intent_flags(self, query: str) -> tuple[bool, bool, bool]:
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
        report_requested = any(
            term in lowered for term in ("보고서", "리포트", "report", "종합")
        )
        return document_requested, web_requested, report_requested

    def _fallback_decision(
        self,
        query: str,
        available_tools: list[str],
        has_documents: bool = False,
    ) -> ResearchToolDecision:
        """Deterministic fallback if structured tool choice fails."""
        tools = []
        document_requested, web_requested, report_requested = self._intent_flags(query)

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

    async def _execute_tools(
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
            tasks.append(("web_search", self._run_web_search(query)))
        if "retriever" in tools:
            tasks.append(("retriever", self._run_retriever(query, session_id, device_id, state)))

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

    async def _run_web_search(self, query: str) -> dict:
        if not self.search_tool:
            return {"tool": "web_search", "query": query, "results": "", "error": "web_search tool is not configured"}
        result = await self.search_tool.execute(query)
        return {"tool": "web_search", "query": query, "results": result}

    async def _run_retriever(
        self,
        query: str,
        session_id: str,
        device_id: str | None,
        state: AgentState,
    ) -> dict:
        if not self.retriever:
            return {"tool": "retriever", "query": query, "results": [], "error": "retriever tool is not configured"}
        if not state.get("has_documents"):
            return {
                "tool": "retriever",
                "query": query,
                "results": [],
                "error": "no documents are available for this session",
            }
        docs = await self.retriever.execute(query, top_k=3, session_id=session_id, device_id=device_id)
        return {"tool": "retriever", "query": query, "results": docs}

    def _format_tool_context(self, tool_results: list[dict]) -> str:
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
                parts.append("[retriever]\n" + self._format_docs(docs))
        return "\n\n---\n\n".join(part for part in parts if part.strip())

    def _format_docs(self, docs: list[dict]) -> str:
        """Format retrieved document chunks."""
        if not docs:
            return "No matching uploaded document chunks were found."
        return "\n\n".join(
            f"[{doc.get('metadata', {}).get('source') or doc.get('metadata', {}).get('filename') or 'doc'}]\n"
            f"{doc.get('content', '')}"
            for doc in docs
            if isinstance(doc, dict)
        )
