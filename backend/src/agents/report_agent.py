"""Report agent for generating comprehensive research reports."""

import re
from typing import override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore
from src.graph.state import AgentState
from src.observability import record_agent_metrics

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


class ReportAgent(BaseAgent):
    """Agent for generating comprehensive research reports from workflow results."""

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "report"

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        memory: MemoryStore = Provide[DIContainer.memory],
        metrics_store=Provide[DIContainer.metrics_store],
    ):
        super().__init__(llm, memory=memory)
        self.metrics_store = metrics_store

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        return """You are an expert research report writer specializing in synthesizing information from multiple sources into comprehensive, well-structured reports.

Your role is to:
1. Analyze research results from various sources (web search, documents, code execution)
2. Synthesize findings into a coherent narrative
3. Structure reports with clear sections and logical flow
4. Maintain academic rigor with proper citations and references

Guidelines:
- Be objective and balanced in presenting information
- Highlight key findings and insights
- Organize content hierarchically with clear headings
- Use bullet points and lists for readability when appropriate
- Include both summary and detailed analysis
- Cite sources appropriately

# 응답 형식 규칙 (CommonMark 마크다운 표준 준수)

## 문장 작성 규칙
- 문장 끝 마침표(., !, ?) 뒤에는 반드시 공백 한 칸 추가
- 한 문장이 끝나면 다음 문장은 새로 시작 (같은 줄에 이어쓰기 금지)

## 제목/소주제 작성
- 주제 변경 시 반드시 줄바꿈으로 구분
- 소주제 앞뒤로 빈 줄 추가
- 계층 구조에 따라 #, ##, ### 사용

## 목록 작성 (CRITICAL)
- 모든 목록 항목은 반드시 새 줄에 작성
- 순서 없는 목록: "- " (하이픈 + 공백)으로 시작
- 순서 있는 목록: "1. " "2. " 형식으로 시작
- 목록 앞뒤로 반드시 빈 줄 추가
- 절대 한 줄에 여러 목록 항목 작성 금지

## 보고서 구조
1. Executive Summary - 핵심 요약 (2-3문단)
2. Introduction - 연구 배경 및 목적
3. Methodology - 사용된 도구와 접근법
4. Findings - 주요 발견사항 (소스별 분류)
5. Analysis - 통합 분석 및 인사이트
6. Conclusion - 결론 및 시사점
7. References - 참고 자료 목록
"""

    def _extract_research_results(self, workflow_context: str) -> dict[str, list[dict]]:
        """Extract research results from workflow context.

        Parses the workflow_context string to identify and extract results
        from different agent types.

        Args:
            workflow_context: The accumulated workflow context string

        Returns:
            Dictionary mapping source types to their results
        """
        results = {
            "web_search": [],
            "rag": [],
            "code": [],
            "chat": [],
        }

        if not workflow_context:
            return results

        # Pattern to match agent results: [agent_name]: content
        pattern = r"\[([^\]]+)\]:\s*([^\[]+)(?=\[|$)"
        matches = re.findall(pattern, workflow_context, re.DOTALL)

        for agent_name, content in matches:
            agent_name = agent_name.strip().lower()
            content = content.strip()

            if not content:
                continue

            entry = {
                "source": agent_name,
                "content": content[:2000],  # Limit content length
            }

            if "web_search" in agent_name:
                results["web_search"].append(entry)
            elif "rag" in agent_name:
                results["rag"].append(entry)
            elif "code" in agent_name:
                results["code"].append(entry)
            elif "chat" in agent_name:
                results["chat"].append(entry)
            elif "previous" in agent_name:
                # Context restored from memory - classify based on content
                if any(
                    kw in content.lower()
                    for kw in ["검색", "search", "웹", "web", "사이트", "site"]
                ):
                    results["web_search"].append(entry)
                elif any(
                    kw in content.lower()
                    for kw in ["문서", "document", "파일", "file", "업로드", "upload"]
                ):
                    results["rag"].append(entry)
                elif any(
                    kw in content.lower()
                    for kw in ["코드", "code", "실행", "execute", "```python", "```javascript"]
                ):
                    results["code"].append(entry)
                else:
                    results["chat"].append(entry)

        return results

    def _classify_results(self, results: dict[str, list[dict]]) -> dict[str, dict]:
        """Classify results by type and extract key information.

        Args:
            results: Dictionary of extracted results by source type

        Returns:
            Classified results with metadata
        """
        classified = {
            "web_search": {
                "type": "external_research",
                "description": "웹 검색을 통한 실시간 정보",
                "items": results.get("web_search", []),
                "count": len(results.get("web_search", [])),
            },
            "rag": {
                "type": "document_research",
                "description": "문서 기반 낸형 검색 결과",
                "items": results.get("rag", []),
                "count": len(results.get("rag", [])),
            },
            "code": {
                "type": "computational_analysis",
                "description": "코드 실행 및 계산 결과",
                "items": results.get("code", []),
                "count": len(results.get("code", [])),
            },
            "chat": {
                "type": "conversational_context",
                "description": "대화 맥락 및 추가 정보",
                "items": results.get("chat", []),
                "count": len(results.get("chat", [])),
            },
        }

        # Filter out empty categories
        return {k: v for k, v in classified.items() if v["count"] > 0}

    def _structure_report(
        self,
        query: str,
        classified_results: dict[str, dict],
    ) -> str:
        """Structure the report sections based on classified results.

        Args:
            query: Original user query
            classified_results: Classified research results

        Returns:
            Structured report outline as string
        """
        sections = []

        # Executive Summary section
        sections.append("## 1. Executive Summary\n")
        sections.append(f"본 보고서는 '{query}'에 대한 연구 결과를 종합적으로 정리한 것입니다. ")

        source_types = []
        if "web_search" in classified_results:
            source_types.append("웹 검색")
        if "rag" in classified_results:
            source_types.append("문서 검색")
        if "code" in classified_results:
            source_types.append("코드 실행")
        if "chat" in classified_results:
            source_types.append("대화 맥락")

        if source_types:
            sections.append(f"다음의 정보 소스를 활용했습니다: {', '.join(source_types)}.\n")

        # Methodology section
        sections.append("\n## 2. Methodology\n")
        sections.append("본 연구에서는 다음의 접근법을 사용했습니다:\n")

        for _source_type, data in classified_results.items():
            sections.append(f"- **{data['description']}**: {data['count']}건의 결과")
        sections.append("")

        # Findings section (grouped by source)
        sections.append("\n## 3. Findings by Source\n")

        for source_type, data in classified_results.items():
            sections.append(
                f"\n### 3.{list(classified_results.keys()).index(source_type) + 1}. {data['description']}\n"
            )

            for i, item in enumerate(data["items"][:3], 1):  # Limit to top 3 per source
                content_preview = item["content"][:300].replace("\n", " ")
                sections.append(f"{i}. {content_preview}...")
            sections.append("")

        # Analysis section placeholder
        sections.append("\n## 4. Integrated Analysis\n")
        sections.append("위의 다양한 소스에서 수집된 정보를 종합 분석한 결과입니다.\n")

        # Conclusion placeholder
        sections.append("\n## 5. Conclusion\n")
        sections.append("연구 결과의 주요 시사점과 결론을 정리합니다.\n")

        # References section
        sections.append("\n## 6. References\n")
        ref_count = 1
        for _source_type, data in classified_results.items():
            for item in data["items"]:
                sections.append(f"[{ref_count}] {item['source']}")
                ref_count += 1
        sections.append("")

        return "\n".join(sections)

    def _format_citations(self, content: str, sources: dict[str, list[dict]]) -> str:
        """Format citations within the report content.

        Args:
            content: Report content
            sources: Source information for citation

        Returns:
            Content with formatted citations
        """
        # Add citation markers for key claims
        # This is a simplified implementation
        return content

    def _build_report_prompt(
        self,
        query: str,
        classified_results: dict[str, dict],
        structure: str,
    ) -> list[dict]:
        """Build the prompt for report generation.

        Args:
            query: Original user query
            classified_results: Classified research results
            structure: Report structure outline

        Returns:
            List of message dictionaries for LLM
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        # Build context from classified results
        context_parts = []
        for _source_type, data in classified_results.items():
            context_parts.append(f"\n=== {data['description']} ===")
            for item in data["items"]:
                context_parts.append(f"[{item['source']}]: {item['content'][:500]}")

        context_text = "\n".join(context_parts)

        user_prompt = f"""사용자 질의: {query}

다음은 워크플로우에서 수집된 연구 결과입니다:

{context_text}

위의 정보를 바탕으로 다음 구조를 따라 종합 보고서를 작성해주세요:

{structure}

보고서 작성 지침:
1. Executive Summary는 핵심 내용을 2-3문단으로 요약
2. 각 소스 유형별로 주요 발견사항을 정리
3. 통합 분석 섹션에서는 다양한 소스의 정보를 연결하여 인사이트 제공
4. 결론에서는 실질적인 시사점 제시
5. 마크다운 형식으로 깔끔하게 작성
6. 문장 끝 마침표 뒤에는 항상 공백 추가
7. 목록은 각 항목을 새 줄에 작성

보고서를 작성해주세요."""

        messages.append({"role": "user", "content": user_prompt})
        return messages

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Generate comprehensive report from workflow context."""
        session_id = state.get("metadata", {}).get("session_id", "default")
        user_id = state.get("metadata", {}).get("user_id")
        workflow_context = state.get("workflow_context", "")

        # Get the original query from messages
        query = ""
        for msg in reversed(state["messages"]):
            content = get_message_content(msg)
            if content and not content.startswith("["):
                query = content
                break

        if not query:
            query = "연구 보고서"

        logger.info(
            "generating_report",
            session_id=session_id,
            has_context=bool(workflow_context),
            query=query[:100],
        )

        # If no workflow context, provide a simple response
        if not workflow_context:
            response = (
                "보고서를 작성하기 위한 연구 결과가 없습니다. "
                "먼저 웹 검색, 문서 검색, 또는 코드 실행을 통해 정보를 수집해주세요."
            )
            return {
                **state,
                "messages": [*state["messages"], {"role": "assistant", "content": response}],
            }

        response = ""
        async with record_agent_metrics(
            self.metrics_store,
            session_id,
            self.name,
            self.llm.config.model,
            user_id,
        ) as metrics:
            try:
                # Step 1: Extract research results from workflow context
                research_results = self._extract_research_results(workflow_context)

                # Step 2: Classify results by type
                classified_results = self._classify_results(research_results)

                if not classified_results:
                    response = (
                        "워크플로우 컨텍스트에서 연구 결과를 추출할 수 없습니다. "
                        "수집된 데이터의 형식을 확인해주세요."
                    )
                    return {
                        **state,
                        "messages": [
                            *state["messages"],
                            {"role": "assistant", "content": response},
                        ],
                    }

                # Step 3: Structure the report
                report_structure = self._structure_report(query, classified_results)

                # Step 4: Build prompt and generate report
                messages = self._build_report_prompt(query, classified_results, report_structure)

                response, usage = await self.llm.generate_with_usage(messages)
                metrics.set_token_count(usage.get("input_tokens", 0), usage.get("output_tokens", 0))

                # Format citations in the response
                response = self._format_citations(response, classified_results)

            except Exception as e:
                logger.error("report_generation_failed", error=str(e), session_id=session_id)
                response = "보고서 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
                metrics.set_error(e)

        # Store in memory if available
        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(session_id, {"role": "assistant", "content": response})

        # Update workflow state
        workflow_updates = self._update_workflow_state(state, response)

        return {
            **state,
            "messages": [*state["messages"], {"role": "assistant", "content": response}],
            **workflow_updates,
        }
