"""Evaluation domain: evaluator base, context, and result models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel, Field

from shared.configuration import EvaluationConfig, ThresholdRule
from shared.types import Transcript


@dataclass(slots=True)
class EvaluationContext:
    """Inputs shared by all evaluators for a run."""

    scenario_name: str
    dataset: list[Transcript]
    config: EvaluationConfig
    # The scenario instance is passed as ``object`` to avoid a hard import cycle;
    # evaluators that need scenario helpers cast it as required.
    scenario: object


class Evaluator(ABC):
    """Base class for all evaluators."""

    name: ClassVar[str]

    @abstractmethod
    def evaluate(self, ctx: EvaluationContext) -> dict[str, float]:
        """Return a mapping of metric name -> value."""
        raise NotImplementedError


class ThresholdOutcome(BaseModel):
    """Result of applying one threshold rule."""

    metric: str
    op: str
    threshold: float
    actual: float
    passed: bool


class EvaluationResult(BaseModel):
    """Full evaluation result, ready to serialize to JSON."""

    name: str
    scenario: str
    metrics: dict[str, float] = Field(default_factory=dict)
    thresholds: list[ThresholdOutcome] = Field(default_factory=list)
    gate_passed: bool = True


_OPS = {
    "gte": lambda a, b: a >= b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "lt": lambda a, b: a < b,
    "eq": lambda a, b: a == b,
}


def apply_thresholds(
    metrics: dict[str, float], rules: list[ThresholdRule]
) -> tuple[list[ThresholdOutcome], bool]:
    """Evaluate release-gate rules against metrics."""
    outcomes: list[ThresholdOutcome] = []
    gate_passed = True
    for rule in rules:
        actual = metrics.get(rule.metric, float("nan"))
        op = _OPS[rule.op]
        passed = bool(actual == actual and op(actual, rule.value))  # NaN-safe
        gate_passed = gate_passed and passed
        outcomes.append(
            ThresholdOutcome(
                metric=rule.metric,
                op=rule.op,
                threshold=rule.value,
                actual=actual,
                passed=passed,
            )
        )
    return outcomes, gate_passed
