"""Token-reduction strategies.

Importing this package registers all token-reduction strategies via the
:mod:`optimization.token_reduction.strategies` import side effect.
"""

from __future__ import annotations

from optimization.token_reduction.strategies import (
    BaselineFullTranscriptStrategy,
    ContextMinimizationStrategy,
    PromptOptimizationStrategy,
    SelectiveExtractionStrategy,
    SummarizeBeforeAnalyzeStrategy,
)

__all__ = [
    "BaselineFullTranscriptStrategy",
    "ContextMinimizationStrategy",
    "PromptOptimizationStrategy",
    "SelectiveExtractionStrategy",
    "SummarizeBeforeAnalyzeStrategy",
]
