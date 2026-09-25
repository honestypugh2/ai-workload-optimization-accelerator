"""Tests for the client-side 429 retry/backoff wrapper."""

from __future__ import annotations

import pytest

from foundry.adapters._retry import RetryingProvider
from shared.exceptions import ProviderError, ThrottlingError, TransientProviderError
from shared.types import ModelRequest, ModelResponse, TokenUsage

_REQUEST = ModelRequest(prompt="hi", task="sentiment")


def _response(deployment: str = "d0") -> ModelResponse:
    return ModelResponse(
        content="{}",
        usage=TokenUsage(prompt_tokens=1, output_tokens=1),
        deployment=deployment,
        latency_ms=1.0,
    )


class _FlakyProvider:
    """Raises ThrottlingError a fixed number of times, then succeeds."""

    def __init__(self, throttles: int, *, retry_after: float | None = None) -> None:
        self._remaining = throttles
        self._retry_after = retry_after
        self.calls = 0

    @property
    def deployment(self) -> str:
        return "flaky"

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self._remaining > 0:
            self._remaining -= 1
            raise ThrottlingError("429", retry_after_seconds=self._retry_after)
        return _response()


def test_retries_until_success() -> None:
    inner = _FlakyProvider(throttles=3)
    delays: list[float] = []
    provider = RetryingProvider(
        inner, max_retries=5, sleep=delays.append, rand=lambda: 1.0, base_backoff_s=0.5
    )

    result = provider.complete(_REQUEST)

    assert result.deployment == "d0"
    assert inner.calls == 4  # 3 throttles + 1 success
    # Exponential backoff with rand()==1.0: 0.5, 1.0, 2.0.
    assert delays == [0.5, 1.0, 2.0]


def test_reraises_after_exhausting_retries() -> None:
    inner = _FlakyProvider(throttles=10)
    provider = RetryingProvider(inner, max_retries=2, sleep=lambda _: None)

    with pytest.raises(ThrottlingError):
        provider.complete(_REQUEST)

    assert inner.calls == 3  # initial + 2 retries


def test_retry_after_takes_precedence() -> None:
    inner = _FlakyProvider(throttles=1, retry_after=7.5)
    delays: list[float] = []
    provider = RetryingProvider(inner, max_retries=3, sleep=delays.append, rand=lambda: 1.0)

    provider.complete(_REQUEST)

    assert delays == [7.5]


def test_non_throttle_errors_propagate_immediately() -> None:
    class _Broken:
        deployment = "broken"

        def complete(self, request: ModelRequest) -> ModelResponse:
            raise ProviderError("boom")

    provider = RetryingProvider(_Broken(), max_retries=5, sleep=lambda _: None)

    with pytest.raises(ProviderError):
        provider.complete(_REQUEST)


def test_transient_provider_errors_retry_until_success() -> None:
    class _FlakyTransient:
        deployment = "flaky"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: ModelRequest) -> ModelResponse:
            self.calls += 1
            if self.calls < 3:
                raise TransientProviderError("Failed to invoke the Azure CLI")
            return _response()

    inner = _FlakyTransient()
    delays: list[float] = []
    provider = RetryingProvider(
        inner, max_retries=5, sleep=delays.append, rand=lambda: 1.0, base_backoff_s=0.5
    )

    result = provider.complete(_REQUEST)

    assert result.deployment == "d0"
    assert inner.calls == 3  # 2 transient failures + 1 success
    assert delays == [0.5, 1.0]  # exponential backoff, no Retry-After hint


def test_transient_provider_errors_reraise_after_exhausting_retries() -> None:
    class _AlwaysTransient:
        deployment = "flaky"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: ModelRequest) -> ModelResponse:
            self.calls += 1
            raise TransientProviderError("Failed to invoke the Azure CLI")

    inner = _AlwaysTransient()
    provider = RetryingProvider(inner, max_retries=2, sleep=lambda _: None)

    with pytest.raises(TransientProviderError):
        provider.complete(_REQUEST)

    assert inner.calls == 3  # initial + 2 retries


def test_deployment_delegates_to_inner() -> None:
    provider = RetryingProvider(_FlakyProvider(throttles=0), sleep=lambda _: None)
    assert provider.deployment == "flaky"


def test_stats_count_observed_throttles_and_retries() -> None:
    inner = _FlakyProvider(throttles=2)
    provider = RetryingProvider(inner, max_retries=5, sleep=lambda _: None, rand=lambda: 1.0)

    provider.complete(_REQUEST)
    provider.complete(_REQUEST)

    stats = provider.stats
    assert stats.attempts == 4  # 2 throttled + 2 successful
    assert stats.throttles == 2
    assert stats.retries == 2
    assert stats.successes == 2
    assert stats.failures == 0
    assert stats.http_429_rate == 0.5
    assert stats.backoff_seconds == 0.5 + 1.0


def test_stats_record_exhausted_retries_as_failure() -> None:
    provider = RetryingProvider(_FlakyProvider(throttles=10), max_retries=1, sleep=lambda _: None)

    with pytest.raises(ThrottlingError):
        provider.complete(_REQUEST)

    stats = provider.stats
    assert stats.attempts == 2
    assert stats.throttles == 2
    assert stats.retries == 1
    assert stats.failures == 1


def test_stats_combine_sums_providers() -> None:
    from foundry.adapters import RetryStats

    total = RetryStats.combine([RetryStats(attempts=2, throttles=1), RetryStats(attempts=3)])
    assert total.attempts == 5
    assert total.throttles == 1
    assert total.http_429_rate == 0.2


class _HttpError(Exception):
    def __init__(self, status_code: int | None) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class APIConnectionError(Exception):
    """Stand-in with the same class name the OpenAI SDK raises on network failure."""


@pytest.mark.parametrize("status", [408, 409, 500, 502, 503, 504])
def test_server_and_timeout_statuses_are_retryable(status: int) -> None:
    from foundry.adapters._retry import is_retryable_server_error

    assert is_retryable_server_error(_HttpError(status))


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 429])
def test_client_errors_and_throttles_are_not_server_retryable(status: int) -> None:
    from foundry.adapters._retry import is_retryable_server_error

    # 429 is handled separately as ThrottlingError so it is counted as throttling.
    assert not is_retryable_server_error(_HttpError(status))


def test_connection_errors_without_status_are_retryable() -> None:
    from foundry.adapters._retry import is_retryable_server_error

    assert is_retryable_server_error(APIConnectionError("reset by peer"))
    assert not is_retryable_server_error(ValueError("bad input"))
