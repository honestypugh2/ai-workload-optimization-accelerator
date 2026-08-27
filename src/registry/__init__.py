"""Plugin registries for scenarios, strategies, and evaluators.

Registration is explicit and side-effect based (decorators), avoiding large
if/else dispatch chains. Modules register their plugins at import time; the CLI
imports the plugin packages to populate the registries.
"""

from registry.evaluator_registry import EvaluatorRegistry, evaluator_registry
from registry.scenario_registry import ScenarioRegistry, scenario_registry
from registry.strategy_registry import StrategyRegistry, strategy_registry

__all__ = [
    "EvaluatorRegistry",
    "ScenarioRegistry",
    "StrategyRegistry",
    "evaluator_registry",
    "scenario_registry",
    "strategy_registry",
]
