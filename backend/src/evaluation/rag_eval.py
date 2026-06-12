"""Offline RAG evaluation dataset runner.

The runner intentionally stays provider-free: it validates a JSONL dataset and
computes retrieval/answer coverage metrics from recorded results. Live model
execution can be added later behind this stable report shape.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    """One recorded RAG evaluation case."""

    question: str
    expected_sources: list[str]
    retrieved_sources: list[str]
    answer: str


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

    if not question:
        raise ValueError(f"Line {line_number}: question is required")
    if not isinstance(data.get("expected_sources", []), list):
        raise ValueError(f"Line {line_number}: expected_sources must be a list")
    if not isinstance(data.get("retrieved_sources", []), list):
        raise ValueError(f"Line {line_number}: retrieved_sources must be a list")

    return EvalCase(
        question=question,
        expected_sources=expected_sources,
        retrieved_sources=retrieved_sources,
        answer=answer,
    )


def evaluate_cases(cases: list[EvalCase]) -> dict[str, Any]:
    """Compute simple RAG regression metrics."""
    if not cases:
        return {
            "case_count": 0,
            "source_hit_rate": 0,
            "answer_coverage_rate": 0,
            "no_answer_rate": 0,
        }

    source_hits = 0
    answer_covered = 0
    no_answer = 0

    for case in cases:
        expected = set(case.expected_sources)
        retrieved = set(case.retrieved_sources)
        if expected and expected & retrieved:
            source_hits += 1
        if case.answer:
            answer_covered += 1
        else:
            no_answer += 1

    total = len(cases)
    return {
        "case_count": total,
        "source_hit_rate": source_hits / total,
        "answer_coverage_rate": answer_covered / total,
        "no_answer_rate": no_answer / total,
    }


def main() -> None:
    """Run the offline RAG evaluation CLI."""
    parser = argparse.ArgumentParser(description="Run offline RAG evaluation metrics")
    parser.add_argument("dataset", type=Path, help="Path to a JSONL dataset")
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    print(json.dumps(evaluate_cases(cases), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
