"""Provenance, observed-vs-modeled metrics, and cost extrapolation on results."""

from __future__ import annotations

from pathlib import Path

import pytest

import benchmarking.infrastructure.providers as provider_wiring
from benchmarking.api import run_benchmark, run_benchmark_file
from foundry.adapters import MockModelProvider, RetryingProvider
from shared.configuration import load_benchmark_config
from shared.exceptions import ThrottlingError
from shared.types import ExecutionMode, ModelRequest, ModelResponse

BENCHMARKS = Path("workload-scenarios/post-call-analytics/benchmarks")


def test_local_result_records_provenance_and_modeled_sources() -> None:
    result = run_benchmark_file(BENCHMARKS / "baseline-batch.yaml")

    assert result.schema_version == 2
    prov = result.provenance
    assert prov is not None
    assert prov.config_path is not None and prov.config_path.endswith("baseline-batch.yaml")
    assert len(prov.config_sha256) == 64
    assert prov.config_execution_mode == "local"
    assert prov.model_deployments == {"baseline": "mock:baseline"}
    assert prov.endpoint_host is None
    assert prov.timing_clock in {"CLOCK_MONOTONIC_RAW", "perf_counter"}
    assert prov.deployment_profile["deployment_count"] >= 1

    m = result.metrics
    assert m.throttling_source == "modeled"
    assert m.timing_source == "modeled"
    assert m.modeled_http_429_rate == m.http_429_rate
    assert m.modeled_batch_completion_seconds == m.batch_completion_seconds
    assert m.observed_http_429_rate is None
    assert m.observed_wall_clock_seconds is None


def test_small_runs_flag_extrapolated_cost() -> None:
    result = run_benchmark_file(BENCHMARKS / "baseline-batch.yaml")  # 40 transcripts
    m = result.metrics
    assert m.cost_extrapolated is True
    assert m.daily_volume == 7000
    assert m.cost_extrapolation_factor == pytest.approx(7000 / 40)
    assert any("extrapolated" in note for note in result.notes)


def test_full_volume_run_is_not_extrapolated(monkeypatch: pytest.MonkeyPatch) -> None:
    from workloads.post_call_analytics.scenario import PostCallAnalyticsScenario

    real_load = PostCallAnalyticsScenario.load_config

    def small_day(self):
        cfg = real_load(self)
        profile = cfg.dataset_profile.model_copy(update={"target_daily_volume": 40})
        return cfg.model_copy(update={"dataset_profile": profile})

    monkeypatch.setattr(PostCallAnalyticsScenario, "load_config", small_day)
    result = run_benchmark_file(BENCHMARKS / "baseline-batch.yaml")  # 40 transcripts
    assert result.metrics.cost_extrapolated is False
    assert result.metrics.cost_extrapolation_factor == 1.0


def test_overrides_are_recorded_and_change_fingerprint() -> None:
    config = load_benchmark_config(BENCHMARKS / "baseline-batch.yaml")
    plain = run_benchmark(config)
    overridden = run_benchmark(
        config.model_copy(update={"transcript_count": 12}),
        overrides={"transcript_count": 12},
        config_execution_mode=config.execution_mode,
    )
    assert plain.provenance is not None and overridden.provenance is not None
    assert overridden.provenance.config_overrides == {"transcript_count": 12}
    assert overridden.provenance.config_sha256 != plain.provenance.config_sha256


class _ThrottleEveryNth:
    """Mock provider that returns HTTP 429 on every ``n``-th attempt."""

    def __init__(self, inner: MockModelProvider, n: int) -> None:
        self._inner = inner
        self._n = n
        self._attempts = 0

    @property
    def deployment(self) -> str:
        return self._inner.deployment

    def complete(self, request: ModelRequest) -> ModelResponse:
        self._attempts += 1
        if self._attempts % self._n == 0:
            raise ThrottlingError("429")
        return self._inner.complete(request)


def test_azure_mode_reports_observed_throttling(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("AIWOA_GATEWAY_KIND", "FOUNDRY_USE_AGENT", "FOUNDRY_PROJECT_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FOUNDRY_MODEL_NAME", "gpt-nano")

    def fake_build_provider(alias, model, token_counter, mode=ExecutionMode.LOCAL):
        inner = _ThrottleEveryNth(MockModelProvider(alias, model, token_counter), n=4)
        return RetryingProvider(inner, sleep=lambda _: None, rand=lambda: 0.0)

    monkeypatch.setattr(provider_wiring, "build_provider", fake_build_provider)
    config = load_benchmark_config(BENCHMARKS / "baseline-batch.yaml")
    result = run_benchmark(config.model_copy(update={"execution_mode": "azure"}))

    m = result.metrics
    assert result.execution_backend == "direct"
    assert m.throttling_source == "observed"
    assert m.timing_source == "observed"
    assert m.observed_http_429_count is not None and m.observed_http_429_count > 0
    assert m.observed_attempts is not None
    assert m.http_429_rate == pytest.approx(
        m.observed_http_429_count / m.observed_attempts, abs=1e-4
    )
    assert m.retry_count == m.observed_retry_count == m.observed_http_429_count
    assert m.batch_completion_seconds == m.observed_wall_clock_seconds
    # Modeled values are still reported side by side for comparison.
    assert m.modeled_http_429_rate is not None
    assert m.modeled_batch_completion_seconds is not None
    assert result.provenance is not None
    assert result.provenance.model_deployments == {"baseline": "gpt-nano"}
    assert any("OBSERVED" in note for note in result.notes)


def test_azure_notes_flag_single_deployment_for_tiered_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in ("AIWOA_GATEWAY_KIND", "FOUNDRY_USE_AGENT", "FOUNDRY_PROJECT_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FOUNDRY_MODEL_NAME", "gpt-nano")

    def fake_build_provider(alias, model, token_counter, mode=ExecutionMode.LOCAL):
        return RetryingProvider(MockModelProvider(alias, model, token_counter))

    monkeypatch.setattr(provider_wiring, "build_provider", fake_build_provider)
    config = load_benchmark_config(BENCHMARKS / "option-b-azure.yaml")
    result = run_benchmark(config.model_copy(update={"transcript_count": 5}))

    assert result.provenance is not None
    assert set(result.provenance.model_deployments.values()) == {"gpt-nano"}
    assert any("tiered routing was not exercised" in note for note in result.notes)
