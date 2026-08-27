"""Registry of evaluator plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from registry._base import Registry

if TYPE_CHECKING:
    from evaluation.domain import Evaluator  # noqa: F401

EvaluatorRegistry = Registry["type[Evaluator]"]

evaluator_registry: EvaluatorRegistry = Registry("evaluator")
