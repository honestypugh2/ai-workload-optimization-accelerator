"""Public evaluation API and regression comparison."""

from __future__ import annotations

from pathlib import Path

from evaluation.application import EvaluationRunner
from evaluation.domain import EvaluationResult
from shared.configuration import EvaluationConfig, load_evaluation_config

__all__ = [
    "EvaluationConfig",
    "EvaluationResult",
    "EvaluationRunner",
    "compare_results",
    "run_evaluation",
    "run_evaluation_file",
]


def run_evaluation(config: EvaluationConfig) -> EvaluationResult:
    """Run an evaluation from a validated configuration object."""
    return EvaluationRunner().run(config)


def run_evaluation_file(path: str | Path) -> EvaluationResult:
    """Load an evaluation configuration file and run it."""
    return run_evaluation(load_evaluation_config(path))


def compare_results(
    baseline: dict[str, float], candidate: dict[str, float]
) -> dict[str, dict[str, float]]:
    """Compute per-metric deltas between two metric maps (regression testing)."""
    keys = sorted(set(baseline) | set(candidate))
    comparison: dict[str, dict[str, float]] = {}
    for key in keys:
        b = baseline.get(key, float("nan"))
        c = candidate.get(key, float("nan"))
        delta = c - b if (b == b and c == c) else float("nan")
        comparison[key] = {"baseline": b, "candidate": c, "delta": delta}
    return comparison
