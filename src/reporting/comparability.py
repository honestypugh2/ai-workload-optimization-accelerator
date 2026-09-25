"""Guards against comparing benchmark results that were not produced alike.

A local simulation, a 25-transcript live smoke run, and a full 7,000-transcript
live batch all serialize to the same result shape, so nothing stops them being
put side by side. These checks surface the differences that make a comparison
misleading (execution mode, provider backend, volume) before it reaches a
scorecard. Pure functions; rendering and exit codes live in the CLI.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

# Volumes within this factor of the baseline are treated as comparable. Beyond it,
# batch time, throughput, and throttling reflect scale rather than architecture.
DEFAULT_MAX_VOLUME_RATIO = 2.0


@dataclass(frozen=True, slots=True)
class RunMeta:
    """Provenance fields of one benchmark result that decide comparability."""

    execution_mode: str | None = None
    execution_backend: str | None = None
    transcripts: int | None = None
    schema_version: int = 1
    throttling_source: str | None = None
    timing_source: str | None = None
    cost_extrapolated: bool | None = None
    model_deployments: dict[str, str] = field(default_factory=dict)
    config_sha256: str | None = None
    config_execution_mode: str | None = None
    generated_at: str | None = None

    @classmethod
    def from_result(cls, data: dict[str, Any]) -> RunMeta:
        metrics = data.get("metrics") or {}
        provenance = data.get("provenance") or {}
        schema_version = int(data.get("schema_version") or 1)
        transcripts = metrics.get("transcripts")
        daily_volume = metrics.get("daily_volume")
        cost_extrapolated = metrics.get("cost_extrapolated")
        if cost_extrapolated is None and isinstance(transcripts, int) and daily_volume:
            cost_extrapolated = transcripts != daily_volume
        return cls(
            execution_mode=data.get("execution_mode"),
            execution_backend=data.get("execution_backend"),
            transcripts=transcripts if isinstance(transcripts, int) else None,
            schema_version=schema_version,
            # v1 results always derived throttling and batch time from the quota model.
            throttling_source=metrics.get("throttling_source") or "modeled",
            timing_source=metrics.get("timing_source") or "modeled",
            cost_extrapolated=cost_extrapolated,
            model_deployments=dict(provenance.get("model_deployments") or {}),
            config_sha256=provenance.get("config_sha256"),
            config_execution_mode=provenance.get("config_execution_mode"),
            generated_at=provenance.get("generated_at"),
        )

    @property
    def is_legacy(self) -> bool:
        return self.schema_version < 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ComparabilityIssue:
    """One reason a run should not be compared directly with the baseline."""

    label: str
    check: str
    message: str
    blocking: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_comparability(
    runs: Sequence[tuple[str, RunMeta | None]],
    *,
    max_volume_ratio: float = DEFAULT_MAX_VOLUME_RATIO,
) -> list[ComparabilityIssue]:
    """Compare each run's provenance with the first benchmark run (the baseline).

    Blocking issues mean the numbers measure different things (mode, backend, or
    scale). Non-blocking issues are caveats a reader should see (legacy results,
    modeled throttling on live runs, extrapolated cost).
    """
    benchmark_runs = [(label, meta) for label, meta in runs if meta is not None]
    issues: list[ComparabilityIssue] = []
    for label, meta in benchmark_runs:
        issues.extend(_caveats(label, meta))
    if len(benchmark_runs) < 2:
        return issues

    base_label, base = benchmark_runs[0]
    for label, meta in benchmark_runs[1:]:
        if meta.execution_mode != base.execution_mode:
            issues.append(
                ComparabilityIssue(
                    label,
                    "execution_mode",
                    f"execution_mode '{meta.execution_mode}' differs from baseline "
                    f"'{base_label}' ('{base.execution_mode}').",
                    blocking=True,
                )
            )
        if meta.execution_backend != base.execution_backend:
            issues.append(
                ComparabilityIssue(
                    label,
                    "execution_backend",
                    f"execution_backend '{meta.execution_backend}' differs from baseline "
                    f"'{base_label}' ('{base.execution_backend}').",
                    blocking=True,
                )
            )
        if meta.throttling_source != base.throttling_source:
            issues.append(
                ComparabilityIssue(
                    label,
                    "throttling_source",
                    f"429/retry metrics are {meta.throttling_source} but the baseline's are "
                    f"{base.throttling_source}.",
                    blocking=True,
                )
            )
        ratio = _volume_ratio(base.transcripts, meta.transcripts)
        if ratio is not None and ratio > max_volume_ratio:
            issues.append(
                ComparabilityIssue(
                    label,
                    "transcripts",
                    f"processed {meta.transcripts:,} transcripts vs the baseline's "
                    f"{base.transcripts:,} ({ratio:,.1f}x apart; limit {max_volume_ratio:g}x).",
                    blocking=True,
                )
            )
    return issues


def has_blocking(issues: Sequence[ComparabilityIssue]) -> bool:
    return any(issue.blocking for issue in issues)


def _caveats(label: str, meta: RunMeta) -> list[ComparabilityIssue]:
    caveats: list[ComparabilityIssue] = []
    if meta.is_legacy:
        caveats.append(
            ComparabilityIssue(
                label,
                "provenance",
                "legacy result with no provenance (config, deployments, git SHA); re-run to "
                "record them.",
                blocking=False,
            )
        )
    if meta.execution_mode == "azure" and meta.throttling_source == "modeled":
        caveats.append(
            ComparabilityIssue(
                label,
                "throttling_source",
                "live Azure run whose 429 rate, retries, and batch time are MODELED, not "
                "observed (produced before observed metrics were recorded).",
                blocking=False,
            )
        )
    if (
        meta.config_execution_mode
        and meta.execution_mode
        and meta.config_execution_mode != meta.execution_mode
    ):
        caveats.append(
            ComparabilityIssue(
                label,
                "mode_override",
                f"config declares execution_mode '{meta.config_execution_mode}' but ran as "
                f"'{meta.execution_mode}' (CLI --mode override).",
                blocking=False,
            )
        )
    if meta.cost_extrapolated:
        caveats.append(
            ComparabilityIssue(
                label,
                "cost_extrapolated",
                f"cost/day and cost/month are extrapolated from {meta.transcripts:,} transcripts.",
                blocking=False,
            )
        )
    distinct = set(meta.model_deployments.values())
    if meta.execution_mode == "azure" and len(meta.model_deployments) > 1 and len(distinct) == 1:
        caveats.append(
            ComparabilityIssue(
                label,
                "model_deployments",
                f"every model alias hit one deployment '{next(iter(distinct))}'; tiered "
                "routing was not exercised live.",
                blocking=False,
            )
        )
    return caveats


def _volume_ratio(a: int | None, b: int | None) -> float | None:
    if not a or not b:
        return None
    return max(a, b) / min(a, b)
