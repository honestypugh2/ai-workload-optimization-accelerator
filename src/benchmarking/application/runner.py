"""Benchmark runner: orchestrates dataset, strategy, routing, and metrics."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from benchmarking.domain import BenchmarkMetrics, BenchmarkResult
from benchmarking.domain.models import MetricSource
from benchmarking.infrastructure import (
    assemble_router,
    build_providers,
    build_quota_model,
    collect_provenance,
    resolve_scenario_deployment_profile,
    task_alias_map,
)
from foundry.adapters import RetryingProvider, RetryStats, resolve_execution_backend
from foundry.model_catalog import ApproxTokenCounter
from observability import get_logger
from observability.metrics import MetricSink, Timer
from observability.tracing import span
from optimization import OptimizationStrategy, PromptBundle, StrategyContext, TranscriptOutcome
from optimization.caching import CacheBundle
from registry.scenario_registry import scenario_registry
from registry.strategy_registry import strategy_registry
from shared.configuration import (
    BenchmarkConfig,
    PricingConfig,
    ScenarioConfig,
    load_pricing_config,
)
from shared.types import ExecutionMode, Transcript
from workloads.base import WorkloadScenario

_logger = get_logger("benchmarking.runner")
_BASE_BACKOFF_MS = 500.0

# Extracts the literal prompt template from a prompt markdown file's first
# fenced code block, so the human-readable docs around it are ignored.
_FENCE_RE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)\n```", re.DOTALL)


def _load_prompt_file(path: Path, fallback: str) -> str:
    """Return the fenced prompt template from ``path``, or ``fallback`` if absent."""
    if not path.exists():
        return fallback
    match = _FENCE_RE.search(path.read_text(encoding="utf-8"))
    return match.group(1).strip("\n") if match else fallback


def _load_prompt_bundle(scenario: WorkloadScenario) -> PromptBundle:
    """Build a PromptBundle from the scenario's prompts/ dir, defaulting per file.

    Lets live runs exercise the production-representative prompts (and system
    message) that live alongside the scenario instead of terse in-code defaults.
    """
    prompts_dir = scenario.root / "prompts"
    defaults = PromptBundle()
    return PromptBundle(
        baseline=_load_prompt_file(prompts_dir / "baseline.md", defaults.baseline),
        optimized=_load_prompt_file(prompts_dir / "optimized.md", defaults.optimized),
        member_id_extraction=_load_prompt_file(
            prompts_dir / "member-id-extraction.md", defaults.member_id_extraction
        ),
        compact=_load_prompt_file(prompts_dir / "compact.md", defaults.compact),
        system=_load_prompt_file(prompts_dir / "system.md", defaults.system),
    )


def _execution_mode(value: str) -> ExecutionMode:
    return ExecutionMode(value)


class BenchmarkRunner:
    """Runs a benchmark configuration end to end and returns a result."""

    def run(
        self,
        config: BenchmarkConfig,
        *,
        config_path: str | Path | None = None,
        overrides: dict[str, Any] | None = None,
        config_execution_mode: str | None = None,
    ) -> BenchmarkResult:
        """Run ``config`` and return a result with full provenance.

        ``config_path``, ``overrides`` and ``config_execution_mode`` describe
        where the config came from and what the caller changed (e.g. CLI
        ``--mode``), so the result records the file's intent alongside what
        actually ran.
        """
        with (
            span(
                "benchmark.run",
                benchmark=config.name,
                strategy=config.strategy,
                routing=config.routing,
                mode=config.execution_mode,
            ),
            Timer() as timer,
        ):
            result = self._run(
                config,
                config_path=config_path,
                overrides=overrides,
                config_execution_mode=config_execution_mode,
            )
        _logger.info("Benchmark '%s' finished in %.2fs", config.name, timer.elapsed_ms / 1000.0)
        return result

    def _run(
        self,
        config: BenchmarkConfig,
        *,
        config_path: str | Path | None,
        overrides: dict[str, Any] | None,
        config_execution_mode: str | None,
    ) -> BenchmarkResult:
        scenario_cls = scenario_registry.get(config.scenario)
        scenario = scenario_cls()
        scenario_config = scenario.load_config()

        mode = _execution_mode(config.execution_mode)
        mapping = self._active_mapping(scenario_config, config)
        token_counter = ApproxTokenCounter()

        providers = build_providers(scenario_config.model_catalog, mapping, token_counter, mode)
        profile = resolve_scenario_deployment_profile(scenario_config, config.deployment_overrides)
        quota = build_quota_model(providers, profile)
        ptu_deployment = sorted(providers)[0]
        router = assemble_router(config.routing, providers, mapping, quota, ptu_deployment)

        caches = CacheBundle.from_flags(config.caching)
        ctx = StrategyContext(
            router=router,
            token_counter=token_counter,
            mapping=mapping,
            caches=caches,
            prompts=_load_prompt_bundle(scenario),
            extractor=scenario.default_extractor(),
            chunker_name=config.chunking,
        )
        strategy = strategy_registry.get(config.strategy)()

        dataset = scenario.generate_dataset(config.transcript_count, seed=config.seed, labeled=True)
        _logger.info(
            "Running benchmark '%s' strategy=%s routing=%s transcripts=%d mode=%s workers=%d",
            config.name,
            config.strategy,
            config.routing,
            len(dataset),
            mode.value,
            config.max_concurrency,
        )

        outcomes, wall_clock_seconds = self._timed_process(
            strategy, dataset, ctx, config.max_concurrency
        )
        observed = self._observed_stats(providers)
        pricing = self._load_pricing(scenario, config)
        metrics = self._aggregate(
            outcomes,
            quota,
            profile,
            scenario_config,
            pricing,
            caches,
            config.max_concurrency,
            observed=observed,
            wall_clock_seconds=wall_clock_seconds,
        )
        models = {
            alias: scenario_config.model_catalog.get(alias)
            for alias in set(task_alias_map(mapping).values())
        }
        provenance = collect_provenance(
            config=config,
            mode=mode,
            scenario_root=scenario.root,
            models=models,
            profile=profile,
            config_path=config_path,
            overrides=overrides,
            config_execution_mode=config_execution_mode,
        )

        return BenchmarkResult(
            name=config.name,
            scenario=config.scenario,
            strategy=config.strategy,
            routing=config.routing,
            execution_mode=mode.value,
            execution_backend=resolve_execution_backend(mode),
            use_optimized_mapping=config.use_optimized_mapping,
            currency=pricing.currency,
            metrics=metrics,
            provenance=provenance,
            notes=self._notes(config, mode, metrics, provenance.model_deployments),
        )

    @classmethod
    def _timed_process(
        cls,
        strategy: OptimizationStrategy,
        dataset: Sequence[Transcript],
        ctx: StrategyContext,
        max_concurrency: int,
    ) -> tuple[list[TranscriptOutcome], float]:
        with (
            span("benchmark.process", transcripts=len(dataset), workers=max_concurrency),
            Timer() as timer,
        ):
            outcomes = cls._process_dataset(strategy, dataset, ctx, max_concurrency)
        return outcomes, timer.elapsed_ms / 1000.0

    @staticmethod
    def _observed_stats(providers: Mapping[str, object]) -> RetryStats | None:
        """Aggregate real call outcomes; ``None`` when no live provider was used."""
        live = [p.stats for p in providers.values() if isinstance(p, RetryingProvider)]
        return RetryStats.combine(live) if live else None

    @staticmethod
    def _process_dataset(
        strategy: OptimizationStrategy,
        dataset: Sequence[Transcript],
        ctx: StrategyContext,
        max_concurrency: int,
    ) -> list[TranscriptOutcome]:
        """Process every transcript, returning outcomes in dataset order.

        Metrics are derived from the ordered outcome list, so concurrent
        execution must preserve input order. ``ThreadPoolExecutor.map`` does
        this while overlapping the I/O-bound model calls in AZURE mode.
        """
        if max_concurrency <= 1 or len(dataset) <= 1:
            return [strategy.process(t, ctx) for t in dataset]
        workers = min(max_concurrency, len(dataset))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda t: strategy.process(t, ctx), dataset))

    @staticmethod
    def _active_mapping(scenario: ScenarioConfig, config: BenchmarkConfig):
        if config.use_optimized_mapping and scenario.optimized_model_mapping is not None:
            return scenario.optimized_model_mapping
        return scenario.model_mapping

    @staticmethod
    def _load_pricing(scenario, config: BenchmarkConfig) -> PricingConfig:
        path = scenario.root / config.pricing_file
        return load_pricing_config(path)

    @staticmethod
    def _notes(
        config: BenchmarkConfig,
        mode: ExecutionMode,
        metrics: BenchmarkMetrics,
        model_deployments: dict[str, str],
    ) -> list[str]:
        notes = []
        if mode is ExecutionMode.LOCAL:
            notes.append("Local synthetic run: no Azure calls, mock provider used.")
        if metrics.throttling_source == "modeled":
            notes.append(
                "HTTP 429, retries, and batch time are MODELED from the TPM quota simulation."
            )
        else:
            notes.append(
                "HTTP 429, retries, and batch time are OBSERVED from live calls and wall clock."
            )
        if metrics.cost_extrapolated:
            notes.append(
                f"Cost/day and cost/month are extrapolated "
                f"x{metrics.cost_extrapolation_factor:,.1f} from {metrics.transcripts} "
                f"transcripts to a {metrics.daily_volume:,}-transcript day."
            )
        distinct_targets = set(model_deployments.values())
        if (
            mode is ExecutionMode.AZURE
            and len(model_deployments) > 1
            and len(distinct_targets) == 1
        ):
            notes.append(
                f"All model aliases ({', '.join(sorted(model_deployments))}) were served by one "
                f"deployment '{next(iter(distinct_targets))}'; tiered routing was not exercised."
            )
        if config.caching:
            notes.append(f"Caching enabled: {', '.join(config.caching)}.")
        if config.chunking:
            notes.append(f"Chunking strategy: {config.chunking}.")
        return notes

    def _aggregate(
        self,
        outcomes: list[TranscriptOutcome],
        quota,
        profile,
        scenario_config: ScenarioConfig,
        pricing: PricingConfig,
        caches: CacheBundle,
        max_concurrency: int,
        *,
        observed: RetryStats | None = None,
        wall_clock_seconds: float | None = None,
    ) -> BenchmarkMetrics:
        sink = MetricSink()
        total_input = 0
        total_output = 0
        total_cost = 0.0
        total_calls = 0
        consumed: dict[str, float] = defaultdict(float)
        extra_latency: dict[str, float] = defaultdict(float)

        effective_tpm = sum(state.tpm_limit for state in quota.states.values()) or 1
        window_tokens = 0
        minutes = 1
        retries = 0
        throttled = 0

        for outcome in outcomes:
            for call in outcome.calls:
                total_calls += 1
                if call.from_cache:
                    continue
                tokens = call.prompt_tokens + call.output_tokens
                if window_tokens + tokens > effective_tpm:
                    minutes += 1
                    window_tokens = 0
                    throttled += 1
                    if profile.retry_with_backoff:
                        retries += 1
                        extra_latency[outcome.transcript_id] += _BASE_BACKOFF_MS
                window_tokens += tokens
                consumed[call.deployment] += tokens
                total_input += call.prompt_tokens
                total_output += call.output_tokens
                total_cost += self._call_cost(call, pricing)

        live = observed if wall_clock_seconds is not None else None
        live_seconds = wall_clock_seconds if live is not None else None
        is_observed = live is not None
        modeled_latencies: list[float] = []
        for outcome in outcomes:
            latency = sum(c.latency_ms for c in outcome.calls)
            modeled_latencies.append(latency + extra_latency.get(outcome.transcript_id, 0.0))
            # Live latencies are real; the simulated backoff penalty only applies to
            # modeled runs (real backoff shows up in the observed wall clock instead).
            sink.observe("latency", latency if is_observed else modeled_latencies[-1])

        transcripts = len(outcomes) or 1
        total_tokens = total_input + total_output
        # Modeled wall-clock is bounded by the slower of two floors: the rate-limit
        # floor (tokens pushed through the TPM ceiling, concurrency-independent) and
        # the compute floor (aggregate call latency shared across parallel workers).
        workers = max(1, min(max_concurrency, transcripts))
        rate_limit_seconds = minutes * 60.0
        compute_seconds = sum(modeled_latencies) / 1000.0
        modeled_batch_seconds = max(rate_limit_seconds, compute_seconds / workers)
        modeled_429_rate = round(throttled / total_calls, 4) if total_calls else 0.0

        if live is not None and live_seconds is not None:
            batch_seconds = live_seconds
            http_429_rate = round(live.http_429_rate, 4)
            retry_count = live.retries
            error_count = live.failures
            queue_depth = live.throttles
        else:
            batch_seconds = modeled_batch_seconds
            http_429_rate = modeled_429_rate
            retry_count = retries
            error_count = 0
            queue_depth = throttled
        batch_minutes = batch_seconds / 60.0 or 1.0
        utilization_minutes = batch_minutes if is_observed else minutes

        utilization = {
            name: round(min(1.0, consumed[name] / (state.tpm_limit * utilization_minutes)), 4)
            for name, state in quota.states.items()
        }

        cost_per_transcript = total_cost / transcripts
        daily_volume = scenario_config.dataset_profile.target_daily_volume
        extrapolation = daily_volume / transcripts
        source: MetricSource = "observed" if is_observed else "modeled"

        return BenchmarkMetrics(
            transcripts=transcripts,
            transcripts_per_minute=round(transcripts / batch_minutes, 3),
            effective_tokens_per_minute=round(total_tokens / batch_minutes, 2),
            p50_latency_ms=round(sink.percentile("latency", 50), 3),
            p95_latency_ms=round(sink.percentile("latency", 95), 3),
            p99_latency_ms=round(sink.percentile("latency", 99), 3),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            average_tokens_per_transcript=round(total_tokens / transcripts, 2),
            estimated_cost=round(total_cost, 6),
            cost_per_transcript=round(cost_per_transcript, 6),
            cost_per_1k_transcripts=round(cost_per_transcript * 1000, 4),
            cost_per_day=round(cost_per_transcript * daily_volume, 2),
            cost_per_month=round(cost_per_transcript * daily_volume * 30, 2),
            http_429_rate=http_429_rate,
            retry_count=retry_count,
            error_count=error_count,
            cache_hit_rate=round(caches.combined_hit_rate, 4),
            deployment_utilization=utilization,
            workload_queue_depth=queue_depth,
            batch_completion_seconds=round(batch_seconds, 2),
            throttling_source=source,
            timing_source=source,
            modeled_http_429_rate=modeled_429_rate,
            modeled_retry_count=retries,
            modeled_batch_completion_seconds=round(modeled_batch_seconds, 2),
            observed_attempts=live.attempts if live else None,
            observed_http_429_count=live.throttles if live else None,
            observed_http_429_rate=http_429_rate if live else None,
            observed_retry_count=live.retries if live else None,
            observed_transient_error_count=live.transient_errors if live else None,
            observed_backoff_seconds=round(live.backoff_seconds, 3) if live else None,
            observed_wall_clock_seconds=round(live_seconds, 2) if live_seconds else None,
            daily_volume=daily_volume,
            cost_extrapolated=transcripts != daily_volume,
            cost_extrapolation_factor=round(extrapolation, 4),
        )

    @staticmethod
    def _call_cost(call, pricing: PricingConfig) -> float:
        try:
            entry = pricing.entry(call.deployment)
        except Exception:
            return 0.0
        return (
            call.prompt_tokens / 1000.0 * entry.input_per_1k
            + call.output_tokens / 1000.0 * entry.output_per_1k
        )
