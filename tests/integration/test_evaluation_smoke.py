"""Evaluation harness smoke tests — offline, using synthetic labeled data."""

from __future__ import annotations

from pathlib import Path

from evaluation.api import compare_results, run_evaluation_file

EVALS = Path("workload-scenarios/post-call-analytics/evaluations")


def test_member_id_evaluation_meets_recall_gate() -> None:
    result = run_evaluation_file(EVALS / "member-id.yaml")
    assert result.metrics["member_id_recall"] >= 0.90
    assert result.gate_passed is True


def test_regression_evaluation_reflects_naive_baseline() -> None:
    result = run_evaluation_file(EVALS / "regression.yaml")
    # The naive baseline should land near the ~30% starting point.
    assert 0.20 <= result.metrics["member_id_recall"] <= 0.45


def test_optimized_beats_baseline_recall() -> None:
    optimized = run_evaluation_file(EVALS / "member-id.yaml").metrics
    baseline = run_evaluation_file(EVALS / "regression.yaml").metrics
    assert optimized["member_id_recall"] > baseline["member_id_recall"] + 0.4


def test_compare_results_reports_positive_delta() -> None:
    comparison = compare_results(
        {"member_id_recall": 0.30},
        {"member_id_recall": 0.93},
    )
    assert comparison["member_id_recall"]["delta"] > 0
