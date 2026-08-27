"""Benchmark harness smoke tests — must run fully offline (no Azure creds)."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarking.api import run_benchmark, run_benchmark_file
from shared.configuration import load_benchmark_config

BENCHMARKS = Path("workload-scenarios/post-call-analytics/benchmarks")


def test_baseline_benchmark_runs_offline() -> None:
    result = run_benchmark_file(BENCHMARKS / "baseline-batch.yaml")
    m = result.metrics
    assert m.effective_tokens_per_minute > 0
    assert m.p50_latency_ms > 0
    assert m.cost_per_month >= 0


def test_baseline_reproduces_throttling() -> None:
    result = run_benchmark_file(BENCHMARKS / "baseline-batch.yaml")
    # The reference baseline is designed to hit its TPM ceiling.
    assert result.metrics.http_429_rate > 0


def test_optimized_benchmark_reduces_tokens() -> None:
    baseline = run_benchmark_file(BENCHMARKS / "baseline-batch.yaml")
    optimized = run_benchmark_file(BENCHMARKS / "token-optimization.yaml")
    assert (
        optimized.metrics.average_tokens_per_transcript
        < baseline.metrics.average_tokens_per_transcript
    )


@pytest.mark.parametrize(
    "config",
    [
        "chunking-comparison.yaml",
        "routing-comparison.yaml",
        "ptu-sizing.yaml",
        "near-real-time-simulation.yaml",
    ],
)
def test_all_benchmark_configs_execute(config: str) -> None:
    result = run_benchmark_file(BENCHMARKS / config)
    assert result.metrics.effective_tokens_per_minute >= 0


def test_concurrency_preserves_metrics() -> None:
    # Concurrent execution must reorder nothing: metrics are derived from the
    # ordered outcome list, so a parallel run must match the sequential run.
    config = load_benchmark_config(BENCHMARKS / "baseline-batch.yaml")
    sequential = run_benchmark(config.model_copy(update={"max_concurrency": 1}))
    concurrent = run_benchmark(config.model_copy(update={"max_concurrency": 8}))
    assert concurrent.metrics == sequential.metrics
