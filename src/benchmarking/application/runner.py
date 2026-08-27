"""Benchmark runner: orchestrates dataset, strategy, routing, and metrics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from benchmarking.domain import BenchmarkMetrics, BenchmarkResult
from benchmarking.infrastructure import (
    assemble_router,
    build_providers,
    build_quota_model,
    resolve_scenario_deployment_profile,
)
from foundry.adapters import resolve_execution_backend
from foundry.model_catalog import ApproxTokenCounter
from observability import get_logger
from observability.metrics import MetricSink
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

_logger = get_logger("benchmarking.runner")
_BASE_BACKOFF_MS = 500.0


def _execution_mode(value: str) -> ExecutionMode:
    return ExecutionMode(value)


class BenchmarkRunner:
    """Runs a benchmark configuration end to end and returns a result."""

    def run(self, config: BenchmarkConfig) -> BenchmarkResult:
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
            prompts=PromptBundle(),
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

        outcomes = self._process_dataset(strategy, dataset, ctx, config.max_concurrency)
        pricing = self._load_pricing(scenario, config)
        metrics = self._aggregate(outcomes, quota, profile, scenario_config, pricing, caches)

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
            notes=self._notes(config, mode),
        )

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
    def _notes(config: BenchmarkConfig, mode: ExecutionMode) -> list[str]:
        notes = []
        if mode is ExecutionMode.LOCAL:
            notes.append("Local synthetic run: no Azure calls, mock provider used.")
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

        for outcome in outcomes:
            latency = sum(c.latency_ms for c in outcome.calls)
            latency += extra_latency.get(outcome.transcript_id, 0.0)
            sink.observe("latency", latency)

        transcripts = len(outcomes) or 1
        total_tokens = total_input + total_output
        batch_seconds = minutes * 60.0 + sum(sink.samples.get("latency", [])) / 1000.0
        batch_minutes = batch_seconds / 60.0 or 1.0

        utilization = {
            name: round(min(1.0, consumed[name] / (state.tpm_limit * minutes)), 4)
            for name, state in quota.states.items()
        }

        cost_per_transcript = total_cost / transcripts
        daily_volume = scenario_config.dataset_profile.target_daily_volume

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
            http_429_rate=round(throttled / total_calls, 4) if total_calls else 0.0,
            retry_count=retries,
            error_count=0,
            cache_hit_rate=round(caches.combined_hit_rate, 4),
            deployment_utilization=utilization,
            workload_queue_depth=throttled,
            batch_completion_seconds=round(batch_seconds, 2),
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
