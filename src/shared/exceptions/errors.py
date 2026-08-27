"""Domain exceptions for the accelerator.

Exceptions are intentionally granular so callers can distinguish configuration
problems from runtime/provider failures.
"""

from __future__ import annotations


class AcceleratorError(Exception):
    """Base class for all accelerator errors."""


class ConfigurationError(AcceleratorError):
    """Raised when a configuration file or object is invalid."""


class ScenarioNotFoundError(AcceleratorError):
    """Raised when a requested workload scenario is not registered."""


class StrategyNotFoundError(AcceleratorError):
    """Raised when a requested optimization strategy is not registered."""


class EvaluatorNotFoundError(AcceleratorError):
    """Raised when a requested evaluator is not registered."""


class ProviderError(AcceleratorError):
    """Raised when a model provider fails to produce a response."""


class TransientProviderError(ProviderError):
    """Raised for transient, retryable provider failures that are not 429s.

    Covers blips such as a momentary credential/CLI token-fetch failure. The
    retry wrapper backs off and retries these without counting them as HTTP 429
    throttling.
    """


class ThrottlingError(ProviderError):
    """Raised to simulate or surface HTTP 429 throttling from a provider.

    ``retry_after_seconds`` carries the server's ``Retry-After`` hint when known
    so a retry wrapper can wait the requested amount before retrying.
    """

    def __init__(self, message: str = "", *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class DatasetError(AcceleratorError):
    """Raised when a dataset cannot be loaded or is structurally invalid."""
