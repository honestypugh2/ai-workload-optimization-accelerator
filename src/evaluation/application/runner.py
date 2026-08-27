"""Evaluation runner: orchestrates evaluators and release gates."""

from __future__ import annotations

from evaluation.domain import (
    EvaluationContext,
    EvaluationResult,
    apply_thresholds,
)
from observability import get_logger
from registry.evaluator_registry import evaluator_registry
from registry.scenario_registry import scenario_registry
from shared.configuration import EvaluationConfig

_logger = get_logger("evaluation.runner")


class EvaluationRunner:
    """Runs an evaluation configuration and applies release-gate thresholds."""

    def run(self, config: EvaluationConfig) -> EvaluationResult:
        scenario_cls = scenario_registry.get(config.scenario)
        scenario = scenario_cls()
        dataset = scenario.generate_dataset(config.dataset_size, seed=config.seed, labeled=True)
        ctx = EvaluationContext(
            scenario_name=config.scenario,
            dataset=dataset,
            config=config,
            scenario=scenario,
        )

        _logger.info(
            "Running evaluation '%s' evaluators=%s dataset=%d",
            config.name,
            ",".join(config.evaluators),
            len(dataset),
        )

        metrics: dict[str, float] = {}
        for name in config.evaluators:
            evaluator = evaluator_registry.get(name)()
            metrics.update(evaluator.evaluate(ctx))

        outcomes, gate_passed = apply_thresholds(metrics, config.thresholds)
        return EvaluationResult(
            name=config.name,
            scenario=config.scenario,
            metrics=metrics,
            thresholds=outcomes,
            gate_passed=gate_passed,
        )
