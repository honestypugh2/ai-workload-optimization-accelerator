"""Provider-agnostic 429 retry/backoff wrapper.

A gateway (LiteLLM or APIM) absorbs most throttling, but it can still return a
429 to the caller when its token-limit trips or every backend is saturated.
This thin wrapper is the client-side safety net that keeps a live run alive.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable

from shared.contracts import ModelProvider
from shared.exceptions import ThrottlingError
from shared.types import ModelRequest, ModelResponse

_DEFAULT_MAX_RETRIES = 5
_DEFAULT_BASE_BACKOFF_S = 0.5
_DEFAULT_MAX_BACKOFF_S = 30.0


class RetryingProvider:
    """Wraps a provider with bounded retry/backoff on HTTP 429.

    Retries only on :class:`ThrottlingError`; all other failures propagate
    immediately. Backoff is exponential with full jitter and capped, and a
    server ``Retry-After`` (when present) takes precedence. ``sleep`` and
    ``rand`` are injectable so tests run deterministically without real delays.
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

    @property
    def deployment(self) -> str:
        return self._inner.deployment

    def complete(self, request: ModelRequest) -> ModelResponse:
        attempt = 0
        while True:
            try:
                return self._inner.complete(request)
            except ThrottlingError as exc:
                if attempt >= self._max_retries:
                    raise
                self._sleep(self._backoff(attempt, exc.retry_after_seconds))
                attempt += 1

    def _backoff(self, attempt: int, retry_after_seconds: float | None) -> float:
        if retry_after_seconds is not None:
            return max(0.0, retry_after_seconds)
        capped = min(self._max_backoff_s, self._base_backoff_s * (2**attempt))
        return self._rand() * capped
