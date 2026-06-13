"""Tests for Research Evidence planning and formatting helpers."""

from src.agents.research_evidence import ResearchEvidenceCollector, ResearchToolDecision


class FakeLLM:
    config = type("Config", (), {"model": "mock-model"})()


def test_detect_intent_identifies_document_web_and_report_requests():
    collector = ResearchEvidenceCollector(llm=FakeLLM())

    intent = collector.detect_intent("최신 뉴스와 업로드 문서를 종합해서 보고서 작성해줘")

    assert intent.document is True
    assert intent.web is True
    assert intent.report is True


def test_fallback_decision_uses_retriever_for_document_request():
    collector = ResearchEvidenceCollector(llm=FakeLLM())

    decision = collector.fallback_decision(
        "업로드한 문서에서 찾아줘",
        available_tools=["web_search", "retriever"],
        has_documents=True,
    )

    assert decision.tools == ["retriever"]
    assert decision.response_mode == "answer"


def test_report_fallback_uses_both_tools_when_documents_are_available():
    collector = ResearchEvidenceCollector(llm=FakeLLM())

    decision = collector.fallback_decision(
        "최신 자료와 문서를 종합해서 보고서 작성해줘",
        available_tools=["web_search", "retriever"],
        has_documents=True,
    )

    assert decision.tools == ["retriever", "web_search"]
    assert decision.response_mode == "report"


def test_explicit_guardrail_adds_missing_retriever_choice():
    collector = ResearchEvidenceCollector(llm=FakeLLM())

    decision = collector.enforce_explicit_tool_intent(
        ResearchToolDecision(tools=[], response_mode="answer", reasoning="under-selected"),
        "rag 문서에서 찾아줘",
        available_tools=["retriever"],
        has_documents=True,
    )

    assert decision.tools == ["retriever"]


def test_normalize_retriever_result_adds_sources_count_and_confidence():
    collector = ResearchEvidenceCollector(llm=FakeLLM())

    normalized = collector.normalize_tool_result(
        {
            "tool": "retriever",
            "query": "문서",
            "results": [
                {
                    "content": "A",
                    "metadata": {"source": "doc-a.txt"},
                    "score": 0.91,
                },
                {
                    "content": "B",
                    "metadata": {"filename": "doc-b.txt"},
                    "score": 0.42,
                },
            ],
        }
    )

    assert normalized["evidence_count"] == 2
    assert normalized["sources"] == ["doc-a.txt", "doc-b.txt"]
    assert normalized["confidence"] == "high"


def test_normalize_web_search_result_extracts_markdown_sources():
    collector = ResearchEvidenceCollector(llm=FakeLLM())

    normalized = collector.normalize_tool_result(
        {
            "tool": "web_search",
            "query": "뉴스",
            "results": "### [Source](https://example.com)\n검색 결과",
        }
    )

    assert normalized["evidence_count"] == 1
    assert normalized["sources"] == ["https://example.com"]
    assert normalized["confidence"] == "medium"


def test_tool_error_result_has_no_evidence_and_error_confidence():
    collector = ResearchEvidenceCollector(llm=FakeLLM())

    normalized = collector.normalize_tool_result(
        {"tool": "retriever", "query": "문서", "results": [], "error": "timeout"}
    )

    assert normalized["evidence_count"] == 0
    assert normalized["confidence"] == "error"
