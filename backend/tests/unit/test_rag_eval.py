"""Tests for offline RAG evaluation metrics."""

from src.evaluation.rag_eval import EvalCase, evaluate_cases


def test_evaluate_cases_reports_source_hit_and_answer_rates():
    report = evaluate_cases(
        [
            EvalCase(
                question="Q1",
                expected_sources=["doc-a"],
                retrieved_sources=["doc-a", "doc-b"],
                answer="answer",
            ),
            EvalCase(
                question="Q2",
                expected_sources=["doc-c"],
                retrieved_sources=["doc-b"],
                answer="",
            ),
        ]
    )

    assert report == {
        "case_count": 2,
        "source_hit_rate": 0.5,
        "answer_coverage_rate": 0.5,
        "no_answer_rate": 0.5,
    }
