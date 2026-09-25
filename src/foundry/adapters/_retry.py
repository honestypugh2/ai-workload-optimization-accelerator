"""Provider-agnostic 429 retry/backoff wrapper.

A gateway (LiteLLM or APIM) absorbs most throttling, but it can still return a
429 to the caller when its token-limit trips or every backend is saturated.
This thin wrapper is the client-side safety net that keeps a live run alive.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from shared.contracts import ModelProvider
from shared.exceptions import ThrottlingError, TransientProviderError
from shared.types import ModelRequest, ModelResponse

_DEFAULT_MAX_RETRIES = 5
_DEFAULT_BASE_BACKOFF_S = 0.5
_DEFAULT_MAX_BACKOFF_S = 30.0

# Adapters disable the OpenAI SDK's built-in retries (which would silently absorb
# 429s before this wrapper could count them), so this wrapper must also cover the
# other failures the SDK used to retry: request timeout, conflict, 5xx, and
# connection/timeout errors raised before any HTTP status exists.
_RETRYABLE_STATUS = frozenset({408, 409})
_RETRYABLE_ERROR_TYPES = frozenset({"APIConnectionError", "APITimeoutError", "InternalServerError"})


def is_retryable_server_error(exc: Exception) -> bool:
    """True for transient server/network failures worth retrying (not 429, not 4xx)."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and (status in _RETRYABLE_STATUS or status >= 500):
        return True
    return type(exc).__name__ in _RETRYABLE_ERROR_TYPES


@dataclass(frozen=True, slots=True)
class RetryStats:
    """Observed (not modeled) call outcomes recorded by :class:`RetryingProvider`."""

    attempts: int = 0
    successes: int = 0
    throttles: int = 0
    transient_errors: int = 0
    retries: int = 0
    failures: int = 0
    backoff_seconds: float = 0.0

    @property
    def http_429_rate(self) -> float:
        """Share of attempts that the service rejected with HTTP 429."""
        return self.throttles / self.attempts if self.attempts else 0.0

    def __add__(self, other: RetryStats) -> RetryStats:
        return RetryStats(
            attempts=self.attempts + other.attempts,
            successes=self.successes + other.successes,
            throttles=self.throttles + other.throttles,
            transient_errors=self.transient_errors + other.transient_errors,
            retries=self.retries + other.retries,
            failures=self.failures + other.failures,
            backoff_seconds=self.backoff_seconds + other.backoff_seconds,
        )

    @classmethod
    def combine(cls, stats: Iterable[RetryStats]) -> RetryStats:
        total = cls()
        for item in stats:
            total = total + item
        return total


class RetryingProvider:
    """Wraps a provider with bounded retry/backoff on HTTP 429.

    Retries on :class:`ThrottlingError` and transient (non-429) provider blips
    such as a momentary credential/CLI token-fetch failure; all other failures
    propagate immediately. Backoff is exponential with full jitter and capped,
    and a server ``Retry-After`` (when present) takes precedence. ``sleep`` and
    ``rand`` are injectable so tests run deterministically without real delays.

    Every attempt is counted in :attr:`stats` so live benchmarks report the
    throttling the service actually returned, rather than a quota simulation.
    Counters are lock-protected because one provider is shared across worker
    threads.
    """

    def __init__(
        self,
        inner: ModelProvider,
        *,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_backoff_s: float = _DEFAULT_BASE_BACKOFF_S,
        max_backoff_s: float = _DEFAULT_MAX_BACKOFF_S,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._inner = inner
        self._max_retries = max(0, max_retries)
        self._base_backoff_s = base_backoff_s
        self._max_backoff_s = max_backoff_s
        self._sleep = sleep
        self._rand = rand
        self._lock = threading.Lock()
        self._stats = RetryStats()

    @property
    def deployment(self) -> str:
        return self._inner.deployment

    @property
    def stats(self) -> RetryStats:
        """Snapshot of observed attempts, throttles, retries, and failures."""
        with self._lock:
            return self._stats

    def _record(self, delta: RetryStats) -> None:
        with self._lock:
            self._stats = self._stats + delta

    def complete(self, request: ModelRequest) -> ModelResponse:
        attempt = 0
        while True:
            try:
                response = self._inner.complete(request)
            except ThrottlingError as exc:
                if attempt >= self._max_retries:
                    self._record(RetryStats(attempts=1, throttles=1, failures=1))
                    raise
                delay = self._backoff(attempt, exc.retry_after_seconds)
                self._record(RetryStats(attempts=1, throttles=1, retries=1, backoff_seconds=delay))
                self._sleep(delay)
                attempt += 1
            except TransientProviderError:
                if attempt >= self._max_retries:
                    self._record(RetryStats(attempts=1, transient_errors=1, failures=1))
                    raise
                delay = self._backoff(attempt, None)
                self._record(
                    RetryStats(attempts=1, transient_errors=1, retries=1, backoff_seconds=delay)
                )
                self._sleep(delay)
                attempt += 1
            except Exception:
                self._record(RetryStats(attempts=1, failures=1))
                raise
            else:
                self._record(RetryStats(attempts=1, successes=1))
                return response

    def _backoff(self, attempt: int, retry_after_seconds: float | None) -> float:
        if retry_after_seconds is not None:
            return max(0.0, retry_after_seconds)
        capped = min(self._max_backoff_s, self._base_backoff_s * (2**attempt))
        return self._rand() * capped
