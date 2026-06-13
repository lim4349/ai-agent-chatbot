"""Tests for offline RAG evaluation metrics."""

from src.evaluation.rag_eval import EvalCase, check_thresholds, evaluate_cases, load_cases


def test_evaluate_cases_reports_source_hit_and_answer_rates():
    report = evaluate_cases(
        [
            EvalCase(
                question="Q1",
                expected_sources=["doc-a"],
                retrieved_sources=["doc-a", "doc-b"],
                answer="answer",
                expected_tools=["retriever"],
                used_tools=["retriever"],
                confidence="high",
                min_confidence="medium",
                expected_pages=[3],
                retrieved_pages=[3],
                expected_heading_paths=["제3장 복리후생"],
                retrieved_heading_paths=["제3장 복리후생"],
                expected_table_terms=["answer"],
                expects_parent_context=True,
                parent_hydrated=True,
                expected_evidence_sources=["doc-a"],
                evidence_items=[{"source": "doc-a", "snippet": "answer 근거"}],
                expected_snippet_terms=["answer"],
            ),
            EvalCase(
                question="Q2",
                expected_sources=["doc-c"],
                retrieved_sources=["doc-b"],
                answer="",
                expected_tools=["retriever"],
                used_tools=["web_search"],
                confidence="low",
                min_confidence="medium",
            ),
        ]
    )

    assert report == {
        "case_count": 2,
        "source_hit_rate": 0.5,
        "answer_coverage_rate": 0.5,
                "no_answer_rate": 0.5,
                "tool_match_rate": 0.5,
                "confidence_pass_rate": 0.5,
        "citation_page_hit_rate": 1.0,
        "heading_path_hit_rate": 1.0,
        "table_answer_coverage_rate": 1.0,
        "parent_hydration_rate": 1.0,
        "evidence_item_source_hit_rate": 1.0,
        "evidence_snippet_coverage_rate": 1.0,
    }


def test_load_cases_parses_tool_and_confidence_expectations(tmp_path):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        (
            '{"question":"업로드 문서 요약해줘",'
            '"expected_sources":["policy.txt"],'
            '"retrieved_sources":["policy.txt"],'
            '"answer":"요약",'
            '"expected_tools":["retriever"],'
            '"used_tools":["retriever"],'
            '"confidence":"medium",'
            '"min_confidence":"low"}\n'
        ),
        encoding="utf-8",
    )

    cases = load_cases(dataset)

    assert cases[0].expected_tools == ["retriever"]
    assert cases[0].used_tools == ["retriever"]
    assert cases[0].confidence == "medium"
    assert cases[0].min_confidence == "low"


def test_load_cases_parses_layout_retrieval_expectations(tmp_path):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        (
            '{"question":"경조사비 금액은?",'
            '"expected_sources":["policy.txt"],'
            '"retrieved_sources":["policy.txt"],'
            '"answer":"결혼 시 50만 원",'
            '"expected_pages":[2],'
            '"retrieved_pages":[2],'
            '"expected_heading_paths":["제3장 복리후생 > 제2조 경조사비"],'
            '"retrieved_heading_paths":["제3장 복리후생 > 제2조 경조사비"],'
            '"expected_table_terms":["50만 원"],'
            '"expects_parent_context":true,'
            '"parent_hydrated":true}\n'
        ),
        encoding="utf-8",
    )

    cases = load_cases(dataset)

    assert cases[0].expected_pages == [2]
    assert cases[0].retrieved_pages == [2]
    assert cases[0].expected_heading_paths == ["제3장 복리후생 > 제2조 경조사비"]
    assert cases[0].retrieved_heading_paths == ["제3장 복리후생 > 제2조 경조사비"]
    assert cases[0].expected_table_terms == ["50만 원"]
    assert cases[0].expects_parent_context is True
    assert cases[0].parent_hydrated is True


def test_load_cases_parses_evidence_item_expectations(tmp_path):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        (
            '{"question":"SLA는?",'
            '"expected_sources":["ops-runbook.md"],'
            '"retrieved_sources":["ops-runbook.md"],'
            '"answer":"SLA는 99.9%",'
            '"expected_evidence_sources":["ops-runbook.md"],'
            '"evidence_items":[{"source":"ops-runbook.md","snippet":"SLA 99.9%"}],'
            '"expected_snippet_terms":["99.9%"]}\n'
        ),
        encoding="utf-8",
    )

    cases = load_cases(dataset)

    assert cases[0].expected_evidence_sources == ["ops-runbook.md"]
    assert cases[0].evidence_items == [{"source": "ops-runbook.md", "snippet": "SLA 99.9%"}]
    assert cases[0].expected_snippet_terms == ["99.9%"]


def test_check_thresholds_reports_failing_metrics():
    failures = check_thresholds(
        {
            "source_hit_rate": 0.5,
            "tool_match_rate": 1.0,
        },
        {
            "source_hit_rate": 0.8,
            "tool_match_rate": 1.0,
        },
    )

    assert failures == ["source_hit_rate=0.500 is below required 0.800"]
