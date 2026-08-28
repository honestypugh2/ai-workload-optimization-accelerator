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


def test_concurrency_preserves_order_invariant_metrics() -> None:
    # Concurrent execution must reorder nothing: order-invariant metrics (tokens,
    # cost, latency percentiles, throttling) are derived from the ordered outcome
    # list and must match a sequential run regardless of worker count.
    config = load_benchmark_config(BENCHMARKS / "baseline-batch.yaml")
    sequential = run_benchmark(config.model_copy(update={"max_concurrency": 1}))
    concurrent = run_benchmark(config.model_copy(update={"max_concurrency": 8}))

    seq, con = sequential.metrics, concurrent.metrics
    assert con.total_input_tokens == seq.total_input_tokens
    assert con.total_output_tokens == seq.total_output_tokens
    assert con.estimated_cost == seq.estimated_cost
    assert con.p50_latency_ms == seq.p50_latency_ms
    assert con.p95_latency_ms == seq.p95_latency_ms
    assert con.p99_latency_ms == seq.p99_latency_ms
    assert con.http_429_rate == seq.http_429_rate


def test_concurrency_reduces_latency_bound_batch_time() -> None:
    # With ample TPM headroom the batch is latency-bound (not throttled), so
    # parallel workers cut wall-clock batch completion and raise throughput.
    config = load_benchmark_config(BENCHMARKS / "baseline-batch.yaml")
    overrides = {
        "deployment_overrides": {"tokens_per_minute_limit": 10**9},
        "transcript_count": 200,
    }
    sequential = run_benchmark(config.model_copy(update={**overrides, "max_concurrency": 1}))
    concurrent = run_benchmark(config.model_copy(update={**overrides, "max_concurrency": 8}))

    assert concurrent.metrics.http_429_rate == 0.0
    assert concurrent.metrics.batch_completion_seconds < sequential.metrics.batch_completion_seconds
    assert concurrent.metrics.transcripts_per_minute > sequential.metrics.transcripts_per_minute
    # Order-invariant metrics stay identical regardless of worker count.
    assert concurrent.metrics.total_input_tokens == sequential.metrics.total_input_tokens
    assert concurrent.metrics.estimated_cost == sequential.metrics.estimated_cost
