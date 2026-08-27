"""Optimization strategies, chunkers, routers, caches, and simulations.

Importing this package registers all built-in optimization strategies into the
``strategy_registry`` via their module import side effects. Downstream code can
then resolve strategies by name without any conditional dispatch.
"""

# Import strategy modules for their registration side effects.
from optimization import (  # noqa: F401
    classification,
    deterministic_extraction,
    token_reduction,
)
from optimization.base import (
    ModelCall,
    OptimizationStrategy,
    PromptBundle,
    StrategyContext,
    TranscriptOutcome,
)

__all__ = [
    "ModelCall",
    "OptimizationStrategy",
    "PromptBundle",
    "StrategyContext",
    "TranscriptOutcome",
]
