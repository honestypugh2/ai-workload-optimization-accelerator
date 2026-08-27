"""Benchmark result and metric domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BenchmarkMetrics(BaseModel):
    """Aggregated metrics for a benchmark run."""

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


class BenchmarkResult(BaseModel):
    """Full benchmark result, ready to serialize to JSON."""

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
    notes: list[str] = Field(default_factory=list)
