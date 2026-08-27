"""Accelerator exception hierarchy."""

from __future__ import annotations

from shared.exceptions.errors import (
    AcceleratorError,
    ConfigurationError,
    DatasetError,
    EvaluatorNotFoundError,
    ProviderError,
    ScenarioNotFoundError,
    StrategyNotFoundError,
    ThrottlingError,
)

__all__ = [
    "AcceleratorError",
    "ConfigurationError",
    "DatasetError",
    "EvaluatorNotFoundError",
    "ProviderError",
    "ScenarioNotFoundError",
    "StrategyNotFoundError",
    "ThrottlingError",
]
