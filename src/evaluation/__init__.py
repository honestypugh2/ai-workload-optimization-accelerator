"""Evaluation harness: local deterministic evaluators and release gates.

Importing this package registers all built-in evaluators via the infrastructure
module's import side effects.
"""

from evaluation import infrastructure  # noqa: F401  (registration side effects)
from evaluation.api import (
    EvaluationConfig,
    EvaluationResult,
    EvaluationRunner,
    compare_results,
    run_evaluation,
    run_evaluation_file,
)

__all__ = [
    "EvaluationConfig",
    "EvaluationResult",
    "EvaluationRunner",
    "compare_results",
    "run_evaluation",
    "run_evaluation_file",
]
