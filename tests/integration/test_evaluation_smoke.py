"""Evaluation harness smoke tests — offline, using synthetic labeled data."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

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


def test_evaluation_emits_tracing_spans_and_timing(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        run_evaluation_file(EVALS / "member-id.yaml")
    messages = [r.getMessage() for r in caplog.records]
    assert any("span.start name=evaluation.run" in m for m in messages)
    assert any("span.start name=evaluation.evaluator" in m for m in messages)
    assert any("span.end name=evaluation.run" in m for m in messages)
    assert any("Evaluation 'member-id' finished in" in m for m in messages)
