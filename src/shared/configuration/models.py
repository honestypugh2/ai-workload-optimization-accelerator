"""Pydantic configuration schemas for external (untrusted) input.

All YAML/JSON that crosses the system boundary is validated here before it is
used by core logic. This keeps validation at the boundary and lets internal code
work with well-formed, typed objects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from shared.exceptions import ConfigurationError


class ModelDefinition(BaseModel):
    """A single logical model in the catalog.

    Model versions are intentionally NOT hardcoded. ``name`` is a deployment
    alias resolved at runtime from configuration/environment.
    """

    name: str = Field(description="Deployment alias (never a hardcoded version).")
    role: str = Field(description="Human-readable role, e.g. 'summarization'.")
    deployment_type: str = Field(default="standard")
    constrained_resource: bool = Field(default=False)
    # Relative cost/latency multipliers used by the local mock provider only.
    relative_latency: float = Field(default=1.0, gt=0)
    relative_quality: float = Field(default=1.0, gt=0)


class ModelCatalog(BaseModel):
    """Catalog of logical models keyed by tier alias (baseline/small/...)."""

    baseline: ModelDefinition
    small: ModelDefinition | None = None
    medium: ModelDefinition | None = None
    large: ModelDefinition | None = None

    def get(self, alias: str) -> ModelDefinition:
        value = getattr(self, alias, None)
        if value is None:
            raise ConfigurationError(f"Model alias '{alias}' is not defined in the catalog.")
        return value


class DeploymentProfile(BaseModel):
    """Represents the throughput/quota constraints of the current state."""

    deployment_count: int = Field(default=1, ge=1)
    tokens_per_minute_limit: int = Field(default=200_000, gt=0)
    requests_per_minute_limit: int = Field(default=600, gt=0)
    shared_quota: bool = Field(default=True)
    retry_with_backoff: bool = Field(default=True)
    max_retries: int = Field(default=5, ge=0)
    ptu_units: int = Field(default=0, ge=0, description="0 => pure Standard/PayGo.")


class DatasetProfile(BaseModel):
    """Statistical profile that keeps synthetic data faithful to the customer."""

    target_daily_volume: int = Field(default=7_000, gt=0)
    average_token_count: int = Field(default=5_000, gt=0)
    size_distribution: dict[str, float] = Field(
        default_factory=lambda: {"small": 0.3, "average": 0.55, "long": 0.15}
    )
    member_id_presence_rate: float = Field(default=0.85, ge=0, le=1)
    baseline_extraction_success: float = Field(default=0.30, ge=0, le=1)
    escalation_rate: float = Field(default=0.18, ge=0, le=1)
    noisy_transcript_rate: float = Field(default=0.35, ge=0, le=1)
    long_transcript_rate: float = Field(default=0.15, ge=0, le=1)
    smoke_scale_factor: float = Field(
        default=0.0035, gt=0, description="Fraction of daily volume for smoke tests."
    )

    @model_validator(mode="after")
    def _check_distribution(self) -> DatasetProfile:
        total = sum(self.size_distribution.values())
        if abs(total - 1.0) > 0.01:
            raise ConfigurationError(f"size_distribution must sum to 1.0, got {total:.3f}.")
        return self


class ModelMapping(BaseModel):
    """Maps workload tasks to model catalog aliases."""

    sentiment_model: str = "baseline"
    escalation_model: str = "baseline"
    summary_model: str = "baseline"
    evidence_model: str = "baseline"
    extraction_model: str = "baseline"


class PricingEntry(BaseModel):
    """Per-model pricing. Prices are configuration-driven, never hardcoded."""

    input_per_1k: float = Field(ge=0)
    output_per_1k: float = Field(ge=0)


class PricingConfig(BaseModel):
    """Configurable pricing table keyed by model alias."""

    currency: str = "USD"
    models: dict[str, PricingEntry] = Field(default_factory=dict)

    def entry(self, alias: str) -> PricingEntry:
        if alias not in self.models:
            raise ConfigurationError(f"No pricing configured for model alias '{alias}'.")
        return self.models[alias]


class ScenarioConfig(BaseModel):
    """Top-level scenario definition (workload-scenarios/*/scenario.yaml)."""

    name: str
    display_name: str
    description: str = ""
    input_data_type: str = "call_transcript"
    expected_outputs: list[str] = Field(default_factory=list)
    benchmark_dimensions: list[str] = Field(default_factory=list)
    evaluation_metrics: list[str] = Field(default_factory=list)
    optimization_variants: list[str] = Field(default_factory=list)
    model_catalog: ModelCatalog
    model_mapping: ModelMapping = Field(default_factory=ModelMapping)
    optimized_model_mapping: ModelMapping | None = None
    deployment_profile: DeploymentProfile = Field(default_factory=DeploymentProfile)
    dataset_profile: DatasetProfile = Field(default_factory=DatasetProfile)


class BenchmarkConfig(BaseModel):
    """A benchmark run definition (benchmarks/*.yaml)."""

    name: str
    description: str = ""
    scenario: str
    execution_mode: str = Field(default="local")
    strategy: str = Field(default="baseline_full_transcript")
    routing: str = Field(default="single_deployment")
    caching: list[str] = Field(default_factory=list)
    chunking: str | None = None
    use_optimized_mapping: bool = False
    transcript_count: int = Field(default=25, gt=0)
    # Number of transcripts processed in parallel. 1 keeps deterministic,
    # sequential execution; higher values overlap real model I/O in AZURE mode.
    max_concurrency: int = Field(default=1, ge=1)
    deployment_overrides: dict[str, Any] = Field(default_factory=dict)
    pricing_file: str = "configs/pricing.example.yaml"
    seed: int = 1234


class ThresholdRule(BaseModel):
    """A single release-gate threshold rule."""

    metric: str
    op: str = Field(pattern="^(gte|lte|gt|lt|eq)$")
    value: float


class EvaluationConfig(BaseModel):
    """An evaluation run definition (evaluations/*.yaml)."""

    name: str
    description: str = ""
    scenario: str
    evaluators: list[str] = Field(default_factory=list)
    dataset_size: int = Field(default=50, gt=0)
    seed: int = 4321
    thresholds: list[ThresholdRule] = Field(default_factory=list)
    # For member-id evaluations: which extractor pipeline to score.
    extractor: str = Field(default="deterministic")


class ScorecardRunSpec(BaseModel):
    """One column of a scorecard: a labelled run and its result files.

    Paths are relative to the scorecard config file's directory (or absolute).
    """

    label: str
    benchmark: str | None = None
    evaluation: str | None = None

    @model_validator(mode="after")
    def _require_a_source(self) -> ScorecardRunSpec:
        if not self.benchmark and not self.evaluation:
            raise ValueError(
                f"Scorecard run '{self.label}' needs a benchmark or evaluation result path."
            )
        return self


class ScorecardConfig(BaseModel):
    """A scorecard definition (scorecards/*.yaml). First run is the baseline."""

    name: str
    description: str = ""
    runs: list[ScorecardRunSpec] = Field(min_length=1)


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file into a plain dict, raising ConfigurationError on failure."""
    p = Path(path)
    if not p.exists():
        raise ConfigurationError(f"Configuration file not found: {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigurationError(f"Invalid YAML in {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"Expected a mapping at the top level of {p}.")
    return data


def load_scenario_config(path: str | Path) -> ScenarioConfig:
    return ScenarioConfig.model_validate(load_yaml(path))


def load_benchmark_config(path: str | Path) -> BenchmarkConfig:
    return BenchmarkConfig.model_validate(load_yaml(path))


def load_evaluation_config(path: str | Path) -> EvaluationConfig:
    return EvaluationConfig.model_validate(load_yaml(path))


def load_scorecard_config(path: str | Path) -> ScorecardConfig:
    return ScorecardConfig.model_validate(load_yaml(path))


def load_pricing_config(path: str | Path) -> PricingConfig:
    return PricingConfig.model_validate(load_yaml(path))
