"""Benchmark result and metric domain models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# Bumped when the result JSON gains fields that consumers (scorecard, UI) rely on.
# v1 results (no ``schema_version``) have no provenance and modeled-only throttling.
RESULT_SCHEMA_VERSION = 2

MetricSource = Literal["modeled", "observed"]


class BenchmarkMetrics(BaseModel):
    """Aggregated metrics for a benchmark run.

    Headline throughput/throttling fields come from ``throttling_source`` and
    ``timing_source``: ``observed`` for live Azure runs (real 429s and wall
    clock), ``modeled`` for local/dry-run runs (TPM quota simulation). Both
    variants are also kept side by side in the ``modeled_*`` / ``observed_*``
    fields so the two can be compared directly.
    """

    transcripts: int
    transcripts_per_minute: float
    effective_tokens_per_minute: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    average_tokens_per_transcript: float
    estimated_cost: float
    cost_per_transcript: float
    cost_per_1k_transcripts: float
    cost_per_day: float
    cost_per_month: float
    http_429_rate: float
    retry_count: int
    error_count: int
    cache_hit_rate: float
    deployment_utilization: dict[str, float] = Field(default_factory=dict)
    workload_queue_depth: int = 0
    batch_completion_seconds: float = 0.0

    throttling_source: MetricSource = "modeled"
    timing_source: MetricSource = "modeled"
    modeled_http_429_rate: float | None = None
    modeled_retry_count: int | None = None
    modeled_batch_completion_seconds: float | None = None
    observed_attempts: int | None = None
    observed_http_429_count: int | None = None
    observed_http_429_rate: float | None = None
    observed_retry_count: int | None = None
    observed_transient_error_count: int | None = None
    observed_backoff_seconds: float | None = None
    observed_wall_clock_seconds: float | None = None

    # cost_per_day/month are cost_per_transcript x daily_volume. When the run
    # processed fewer transcripts than a daily batch, they are extrapolated.
    daily_volume: int | None = None
    cost_extrapolated: bool = False
    cost_extrapolation_factor: float = 1.0


class RunProvenance(BaseModel):
    """How, where, and from what inputs a benchmark result was produced."""

    generated_at: str
    accelerator_version: str | None = None
    git_commit: str | None = None
    git_dirty: bool | None = None
    config_path: str | None = None
    config_sha256: str
    config_overrides: dict[str, Any] = Field(default_factory=dict)
    config_execution_mode: str | None = None
    effective_config: dict[str, Any] = Field(default_factory=dict)
    scenario_sha256: str | None = None
    pricing_file: str | None = None
    pricing_sha256: str | None = None
    deployment_profile: dict[str, Any] = Field(default_factory=dict)
    model_deployments: dict[str, str] = Field(default_factory=dict)
    endpoint_host: str | None = None
    # Clock used for latency and wall-clock; see shared.timing for why it matters.
    timing_clock: str | None = None


class BenchmarkResult(BaseModel):
    """Full benchmark result, ready to serialize to JSON."""

    schema_version: int = RESULT_SCHEMA_VERSION
    name: str
    scenario: str
    strategy: str
    routing: str
    execution_mode: str
    # Provenance: which provider path produced the result — "local" (mock),
    # "direct" (Foundry model inference), "agent" (Foundry agent runtime), or
    # "gateway:<kind>" (LiteLLM/APIM). Records hidden runtime/env state.
    execution_backend: str = "unknown"
    use_optimized_mapping: bool
    currency: str
    metrics: BenchmarkMetrics
    provenance: RunProvenance | None = None
    notes: list[str] = Field(default_factory=list)
