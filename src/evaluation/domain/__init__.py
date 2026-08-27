"""Evaluation domain: evaluator base type, results, and threshold logic."""

from __future__ import annotations

from evaluation.domain.models import (
    EvaluationContext,
    EvaluationResult,
    Evaluator,
    ThresholdOutcome,
    apply_thresholds,
)

__all__ = [
    "EvaluationContext",
    "EvaluationResult",
    "Evaluator",
    "ThresholdOutcome",
    "apply_thresholds",
]
