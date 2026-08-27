"""Deterministic classification pre-filters and the strategy that uses them.

Importing this package registers the ``dynamic_prompt_construction`` strategy via
the :mod:`optimization.classification.strategy` import side effect.
"""

from __future__ import annotations

from optimization.classification.classifiers import (
    ClassificationResult,
    EscalationRulePrefilter,
    KeywordIntentClassifier,
)
from optimization.classification.strategy import DynamicPromptConstructionStrategy

__all__ = [
    "ClassificationResult",
    "DynamicPromptConstructionStrategy",
    "EscalationRulePrefilter",
    "KeywordIntentClassifier",
]
