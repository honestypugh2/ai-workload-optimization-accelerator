"""Registry of optimization strategy plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from registry._base import Registry

if TYPE_CHECKING:
    from optimization.base import OptimizationStrategy  # noqa: F401

StrategyRegistry = Registry["type[OptimizationStrategy]"]

strategy_registry: StrategyRegistry = Registry("strategy")
