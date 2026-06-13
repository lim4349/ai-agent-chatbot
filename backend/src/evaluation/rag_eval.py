"""Offline RAG evaluation dataset runner.

The runner intentionally stays provider-free: it validates a JSONL dataset and
computes retrieval/answer coverage metrics from recorded results. Live model
execution can be added later behind this stable report shape.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIDENCE_ORDER = {
    "none": 0,
    "error": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


@dataclass(frozen=True)
class EvalCase:
    """One recorded RAG evaluation case."""

    question: str
    expected_sources: list[str]
    retrieved_sources: list[str]
    answer: str
    expected_tools: list[str] = field(default_factory=list)
    used_tools: list[str] = field(default_factory=list)
    confidence: str = "none"
    min_confidence: str = "none"
    expected_pages: list[int] = field(default_factory=list)
    retrieved_pages: list[int] = field(default_factory=list)
    expected_heading_paths: list[str] = field(default_factory=list)
    retrieved_heading_paths: list[str] = field(default_factory=list)
    expected_table_terms: list[str] = field(default_factory=list)
    expects_parent_context: bool = False
    parent_hydrated: bool = False
    expected_evidence_sources: list[str] = field(default_factory=list)
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    expected_snippet_terms: list[str] = field(default_factory=list)


def load_cases(path: Path) -> list[EvalCase]:
    """Load JSONL evaluation cases."""
    cases = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        data = json.loads(line)
        cases.append(parse_case(data, line_number))
    return cases


def parse_case(data: dict[str, Any], line_number: int) -> EvalCase:
    """Parse and validate one evaluation case."""
    question = str(data.get("question") or "").strip()
    answer = str(data.get("answer") or "").strip()
    expected_sources = [str(source) for source in data.get("expected_sources", [])]
    retrieved_sources = [str(source) for source in data.get("retrieved_sources", [])]
    expected_tools = [str(tool) for tool in data.get("expected_tools", [])]
    used_tools = [str(tool) for tool in data.get("used_tools", [])]
    confidence = str(data.get("confidence") or "none").strip()
    min_confidence = str(data.get("min_confidence") or "none").strip()
    expected_pages = [int(page) for page in data.get("expected_pages", [])]
    retrieved_pages = [int(page) for page in data.get("retrieved_pages", [])]
    expected_heading_paths = [str(path) for path in data.get("expected_heading_paths", [])]
    retrieved_heading_paths = [str(path) for path in data.get("retrieved_heading_paths", [])]
    expected_table_terms = [str(term) for term in data.get("expected_table_terms", [])]
    expects_parent_context = bool(data.get("expects_parent_context", False))
    parent_hydrated = bool(data.get("parent_hydrated", False))
    expected_evidence_sources = [str(source) for source in data.get("expected_evidence_sources", [])]
    evidence_items = list(data.get("evidence_items", []))
    expected_snippet_terms = [str(term) for term in data.get("expected_snippet_terms", [])]

    if not question:
        raise ValueError(f"Line {line_number}: question is required")
    if not isinstance(data.get("expected_sources", []), list):
        raise ValueError(f"Line {line_number}: expected_sources must be a list")
    if not isinstance(data.get("retrieved_sources", []), list):
        raise ValueError(f"Line {line_number}: retrieved_sources must be a list")
    if not isinstance(data.get("expected_tools", []), list):
        raise ValueError(f"Line {line_number}: expected_tools must be a list")
    if not isinstance(data.get("used_tools", []), list):
        raise ValueError(f"Line {line_number}: used_tools must be a list")
    if not isinstance(data.get("expected_pages", []), list):
        raise ValueError(f"Line {line_number}: expected_pages must be a list")
    if not isinstance(data.get("retrieved_pages", []), list):
        raise ValueError(f"Line {line_number}: retrieved_pages must be a list")
    if not isinstance(data.get("expected_heading_paths", []), list):
        raise ValueError(f"Line {line_number}: expected_heading_paths must be a list")
    if not isinstance(data.get("retrieved_heading_paths", []), list):
        raise ValueError(f"Line {line_number}: retrieved_heading_paths must be a list")
    if not isinstance(data.get("expected_table_terms", []), list):
        raise ValueError(f"Line {line_number}: expected_table_terms must be a list")
    if not isinstance(data.get("expected_evidence_sources", []), list):
        raise ValueError(f"Line {line_number}: expected_evidence_sources must be a list")
    if not isinstance(data.get("evidence_items", []), list):
        raise ValueError(f"Line {line_number}: evidence_items must be a list")
    if not all(isinstance(item, dict) for item in evidence_items):
        raise ValueError(f"Line {line_number}: evidence_items must contain objects")
    if not isinstance(data.get("expected_snippet_terms", []), list):
        raise ValueError(f"Line {line_number}: expected_snippet_terms must be a list")
    if confidence not in CONFIDENCE_ORDER:
        raise ValueError(f"Line {line_number}: confidence must be one of {confidence_values()}")
    if min_confidence not in CONFIDENCE_ORDER:
        raise ValueError(f"Line {line_number}: min_confidence must be one of {confidence_values()}")

    return EvalCase(
        question=question,
        expected_sources=expected_sources,
        retrieved_sources=retrieved_sources,
        answer=answer,
        expected_tools=expected_tools,
        used_tools=used_tools,
        confidence=confidence,
        min_confidence=min_confidence,
        expected_pages=expected_pages,
        retrieved_pages=retrieved_pages,
        expected_heading_paths=expected_heading_paths,
        retrieved_heading_paths=retrieved_heading_paths,
        expected_table_terms=expected_table_terms,
        expects_parent_context=expects_parent_context,
        parent_hydrated=parent_hydrated,
        expected_evidence_sources=expected_evidence_sources,
        evidence_items=evidence_items,
        expected_snippet_terms=expected_snippet_terms,
    )


def evaluate_cases(cases: list[EvalCase]) -> dict[str, Any]:
    """Compute simple RAG regression metrics."""
    if not cases:
        return {
            "case_count": 0,
            "source_hit_rate": 0,
            "answer_coverage_rate": 0,
            "no_answer_rate": 0,
            "tool_match_rate": 0,
            "confidence_pass_rate": 0,
            "citation_page_hit_rate": 0,
            "heading_path_hit_rate": 0,
            "table_answer_coverage_rate": 0,
            "parent_hydration_rate": 0,
            "evidence_item_source_hit_rate": 0,
            "evidence_snippet_coverage_rate": 0,
        }

    source_hits = 0
    source_expectations = 0
    answer_covered = 0
    no_answer = 0
    tool_expectations = 0
    tool_matches = 0
    confidence_expectations = 0
    confidence_passes = 0
    page_expectations = 0
    page_hits = 0
    heading_expectations = 0
    heading_hits = 0
    table_expectations = 0
    table_passes = 0
    parent_expectations = 0
    parent_passes = 0
    evidence_item_source_expectations = 0
    evidence_item_source_hits = 0
    snippet_expectations = 0
    snippet_passes = 0

    for case in cases:
        expected = set(case.expected_sources)
        retrieved = set(case.retrieved_sources)
        if expected:
            source_expectations += 1
            if expected & retrieved:
                source_hits += 1
        if case.answer:
            answer_covered += 1
        else:
            no_answer += 1
        if case.expected_tools:
            tool_expectations += 1
            if case.expected_tools == case.used_tools:
                tool_matches += 1
        if case.min_confidence != "none":
            confidence_expectations += 1
            if CONFIDENCE_ORDER[case.confidence] >= CONFIDENCE_ORDER[case.min_confidence]:
                confidence_passes += 1
        if case.expected_pages:
            page_expectations += 1
            if set(case.expected_pages) & set(case.retrieved_pages):
                page_hits += 1
        if case.expected_heading_paths:
            heading_expectations += 1
            if set(case.expected_heading_paths) & set(case.retrieved_heading_paths):
                heading_hits += 1
        if case.expected_table_terms:
            table_expectations += 1
            answer = case.answer.lower()
            if all(term.lower() in answer for term in case.expected_table_terms):
                table_passes += 1
        if case.expects_parent_context:
            parent_expectations += 1
            if case.parent_hydrated:
                parent_passes += 1
        if case.expected_evidence_sources:
            evidence_item_source_expectations += 1
            item_sources = {
                str(item.get("source", ""))
                for item in case.evidence_items
                if isinstance(item, dict)
            }
            if set(case.expected_evidence_sources) & item_sources:
                evidence_item_source_hits += 1
        if case.expected_snippet_terms:
            snippet_expectations += 1
            snippets = " ".join(
                str(item.get("snippet", ""))
                for item in case.evidence_items
                if isinstance(item, dict)
            ).lower()
            if all(term.lower() in snippets for term in case.expected_snippet_terms):
                snippet_passes += 1

    total = len(cases)
    return {
        "case_count": total,
        "source_hit_rate": safe_rate(source_hits, source_expectations),
        "answer_coverage_rate": answer_covered / total,
        "no_answer_rate": no_answer / total,
        "tool_match_rate": safe_rate(tool_matches, tool_expectations),
        "confidence_pass_rate": safe_rate(confidence_passes, confidence_expectations),
        "citation_page_hit_rate": safe_rate(page_hits, page_expectations),
        "heading_path_hit_rate": safe_rate(heading_hits, heading_expectations),
        "table_answer_coverage_rate": safe_rate(table_passes, table_expectations),
        "parent_hydration_rate": safe_rate(parent_passes, parent_expectations),
        "evidence_item_source_hit_rate": safe_rate(
            evidence_item_source_hits,
            evidence_item_source_expectations,
        ),
        "evidence_snippet_coverage_rate": safe_rate(snippet_passes, snippet_expectations),
    }


def confidence_values() -> str:
    """Return confidence values for validation messages."""
    return ", ".join(CONFIDENCE_ORDER)


def safe_rate(numerator: int, denominator: int) -> float:
    """Return a rate without dividing by zero."""
    if denominator == 0:
        return 0
    return numerator / denominator


def check_thresholds(report: dict[str, Any], thresholds: dict[str, float]) -> list[str]:
    """Return threshold failure messages for an evaluation report."""
    failures = []
    for metric, minimum in thresholds.items():
        actual = float(report.get(metric, 0))
        if actual < minimum:
            failures.append(f"{metric}={actual:.3f} is below required {minimum:.3f}")
    return failures


def main() -> None:
    """Run the offline RAG evaluation CLI."""
    parser = argparse.ArgumentParser(description="Run offline RAG evaluation metrics")
    parser.add_argument("dataset", type=Path, help="Path to a JSONL dataset")
    parser.add_argument("--min-source-hit-rate", type=float, default=None)
    parser.add_argument("--min-answer-coverage-rate", type=float, default=None)
    parser.add_argument("--max-no-answer-rate", type=float, default=None)
    parser.add_argument("--min-tool-match-rate", type=float, default=None)
    parser.add_argument("--min-confidence-pass-rate", type=float, default=None)
    parser.add_argument("--min-citation-page-hit-rate", type=float, default=None)
    parser.add_argument("--min-heading-path-hit-rate", type=float, default=None)
    parser.add_argument("--min-table-answer-coverage-rate", type=float, default=None)
    parser.add_argument("--min-parent-hydration-rate", type=float, default=None)
    parser.add_argument("--min-evidence-item-source-hit-rate", type=float, default=None)
    parser.add_argument("--min-evidence-snippet-coverage-rate", type=float, default=None)
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    report = evaluate_cases(cases)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    thresholds = {
        key: value
        for key, value in {
            "source_hit_rate": args.min_source_hit_rate,
            "answer_coverage_rate": args.min_answer_coverage_rate,
            "tool_match_rate": args.min_tool_match_rate,
            "confidence_pass_rate": args.min_confidence_pass_rate,
            "citation_page_hit_rate": args.min_citation_page_hit_rate,
            "heading_path_hit_rate": args.min_heading_path_hit_rate,
            "table_answer_coverage_rate": args.min_table_answer_coverage_rate,
            "parent_hydration_rate": args.min_parent_hydration_rate,
            "evidence_item_source_hit_rate": args.min_evidence_item_source_hit_rate,
            "evidence_snippet_coverage_rate": args.min_evidence_snippet_coverage_rate,
        }.items()
        if value is not None
    }
    failures = check_thresholds(report, thresholds)
    if args.max_no_answer_rate is not None:
        actual = float(report.get("no_answer_rate", 0))
        if actual > args.max_no_answer_rate:
            failures.append(
                f"no_answer_rate={actual:.3f} is above allowed {args.max_no_answer_rate:.3f}"
            )

    if failures:
        for failure in failures:
            print(f"FAILED: {failure}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
