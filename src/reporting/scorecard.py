"""Combined operations + cost + evaluation scorecard.

Brings benchmark (operational + cost) metrics and evaluation (quality) metrics
into a single side-by-side view so every run can be compared on all dimensions
at once. Pure functions here; rendering lives in the CLI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Category = Literal["Operations", "Cost", "Quality"]
Source = Literal["benchmark", "evaluation"]


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """Definition of one scorecard metric row."""

    key: str
    label: str
    category: Category
    source: Source
    unit: str = ""
    higher_is_better: bool = True


# Curated, ordered set of metrics that matter for the assessment KPIs.
# Benchmark keys read from the nested ``metrics`` object; evaluation keys read
# from the flat ``metrics`` map. Unknown/missing metrics are simply skipped.
METRIC_SPECS: tuple[MetricSpec, ...] = (
    # --- Operations ---
    MetricSpec(
        "batch_completion_seconds", "Batch completion", "Operations", "benchmark", "s", False
    ),
    MetricSpec("transcripts_per_minute", "Throughput", "Operations", "benchmark", "tx/min", True),
    MetricSpec(
        "effective_tokens_per_minute", "Effective TPM", "Operations", "benchmark", "tok/min", True
    ),
    MetricSpec("p95_latency_ms", "p95 latency", "Operations", "benchmark", "ms", False),
    MetricSpec("http_429_rate", "429 rate", "Operations", "benchmark", "rate", False),
    MetricSpec("retry_count", "Retries", "Operations", "benchmark", "", False),
    MetricSpec("cache_hit_rate", "Cache hit rate", "Operations", "benchmark", "rate", True),
    # --- Cost ---
    MetricSpec(
        "average_tokens_per_transcript", "Tokens / transcript", "Cost", "benchmark", "tok", False
    ),
    MetricSpec("cost_per_transcript", "Cost / transcript", "Cost", "benchmark", "$", False),
    MetricSpec("cost_per_day", "Cost / day", "Cost", "benchmark", "$", False),
    MetricSpec("cost_per_month", "Cost / month", "Cost", "benchmark", "$", False),
    # --- Quality (evaluation) ---
    MetricSpec("member_id_recall", "Member-ID recall", "Quality", "evaluation", "rate", True),
    MetricSpec("member_id_precision", "Member-ID precision", "Quality", "evaluation", "rate", True),
    MetricSpec(
        "member_id_false_positive_rate", "Member-ID FPR", "Quality", "evaluation", "rate", False
    ),
    MetricSpec(
        "member_id_false_negative_rate", "Member-ID FNR", "Quality", "evaluation", "rate", False
    ),
    MetricSpec(
        "extraction_success_rate", "Extraction success", "Quality", "evaluation", "rate", True
    ),
    MetricSpec("escalation_accuracy", "Escalation accuracy", "Quality", "evaluation", "rate", True),
    MetricSpec(
        "structured_output_validity",
        "Structured-output validity",
        "Quality",
        "evaluation",
        "rate",
        True,
    ),
)


@dataclass(frozen=True, slots=True)
class ScorecardRun:
    """One column of the scorecard: a labelled run and its metrics."""

    label: str
    benchmark: dict[str, float] = field(default_factory=dict)
    evaluation: dict[str, float] = field(default_factory=dict)

    def value(self, spec: MetricSpec) -> float | None:
        source = self.benchmark if spec.source == "benchmark" else self.evaluation
        raw = source.get(spec.key)
        return float(raw) if isinstance(raw, (int, float)) else None


@dataclass(frozen=True, slots=True)
class ScorecardRow:
    """A single metric across all runs, with a delta vs the baseline column."""

    spec: MetricSpec
    values: tuple[float | None, ...]

    @property
    def baseline(self) -> float | None:
        return self.values[0] if self.values else None

    @property
    def latest(self) -> float | None:
        return self.values[-1] if self.values else None

    @property
    def delta(self) -> float | None:
        """Latest minus baseline (raw difference)."""
        if self.baseline is None or self.latest is None:
            return None
        return self.latest - self.baseline

    @property
    def improved(self) -> bool | None:
        """Whether the latest value is better than the baseline for this metric."""
        if self.delta is None or self.delta == 0.0:
            return None if self.delta is None else False
        going_up = self.delta > 0
        return going_up == self.spec.higher_is_better


@dataclass(frozen=True, slots=True)
class Scorecard:
    """A full ops + cost + quality comparison across runs."""

    runs: tuple[ScorecardRun, ...]
    rows: tuple[ScorecardRow, ...]

    def rows_for(self, category: Category) -> list[ScorecardRow]:
        return [row for row in self.rows if row.spec.category == category]


def build_scorecard(runs: list[ScorecardRun]) -> Scorecard:
    """Assemble a scorecard, keeping only metrics present in at least one run."""
    rows: list[ScorecardRow] = []
    for spec in METRIC_SPECS:
        values = tuple(run.value(spec) for run in runs)
        if all(v is None for v in values):
            continue
        rows.append(ScorecardRow(spec=spec, values=values))
    return Scorecard(runs=tuple(runs), rows=tuple(rows))


def _extract_benchmark_metrics(data: dict) -> dict[str, float]:
    metrics = data.get("metrics", {})
    return {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))}


def _extract_evaluation_metrics(data: dict) -> dict[str, float]:
    metrics = data.get("metrics", {})
    return {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))}


def load_run(
    label: str,
    benchmark_path: str | Path | None = None,
    evaluation_path: str | Path | None = None,
) -> ScorecardRun:
    """Load a scorecard run from benchmark and/or evaluation result JSON files."""
    benchmark: dict[str, float] = {}
    evaluation: dict[str, float] = {}
    if benchmark_path is not None:
        data = json.loads(Path(benchmark_path).read_text(encoding="utf-8"))
        benchmark = _extract_benchmark_metrics(data)
    if evaluation_path is not None:
        data = json.loads(Path(evaluation_path).read_text(encoding="utf-8"))
        evaluation = _extract_evaluation_metrics(data)
    return ScorecardRun(label=label, benchmark=benchmark, evaluation=evaluation)
