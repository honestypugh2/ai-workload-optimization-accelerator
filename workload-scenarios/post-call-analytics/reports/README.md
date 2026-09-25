# Reports

Benchmark and evaluation results are written here as JSON:

- `<name>.<mode>.result.json` — benchmark runs (`aiwoa benchmark run`), e.g.
  `option-b-azure.local.result.json` (modeled) vs `option-b-azure.azure.result.json`
  (live). The mode suffix comes from the mode that actually ran, not the config.
- `*.eval.json` — evaluation runs (`aiwoa evaluate run`)
- `scorecard.json` — combined ops + cost + quality scorecard (`aiwoa report scorecard`)

## Example output

Running a benchmark prints a summary table and writes the JSON result:

```console
$ uv run aiwoa benchmark run --scenario post-call-analytics \
    --config workload-scenarios/post-call-analytics/benchmarks/option-b-azure.yaml --mode local

           Benchmark: option-b-azure
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric                 ┃               Value ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ Mode / backend         │       local / local │
│ 429 / timing source    │   modeled / modeled │
│ Strategy               │ deterministic_first │
│ Routing                │          task_based │
│ Transcripts            │                7000 │
│ Transcripts/min        │               89.62 │
│ Effective TPM          │           1,049,010 │
│ p50 / p95 / p99 (ms)   │ 289.4 / 462.7 / 538.6 │
│ Input tokens           │          78,749,668 │
│ Output tokens          │           3,184,683 │
│ Avg tokens/transcript  │              11,705 │
│ Cost/day (USD)         │               34.72 │
│ Cost/month (USD)       │            1,041.53 │
│ Cost extrapolated      │                  no │
│ HTTP 429 rate          │                0.1% │
│ Retries                │                  41 │
│ Cache hit rate         │                0.0% │
│ Queue depth            │                  41 │
└────────────────────────┴─────────────────────┘
• Local synthetic run: no Azure calls, mock provider used.
• HTTP 429, retries, and batch time are MODELED from the TPM quota simulation.
• Caching enabled: prompt, result, metadata.
Result written to workload-scenarios/post-call-analytics/reports/option-b-azure.local.result.json
```

The written `*.result.json` (annotated; comments are for docs only — real JSON
has none):

```jsonc
{
  "schema_version": 2,                 // 2 = has provenance + modeled/observed split
  "name": "option-b-azure",
  "scenario": "post-call-analytics",
  "strategy": "deterministic_first",   // optimization strategy applied
  "routing": "task_based",             // how tasks were routed to deployments
  "execution_mode": "local",           // local (modeled) | dry-run | azure (live)
  "execution_backend": "local",        // provenance: local | direct | agent | gateway:<kind>
  "use_optimized_mapping": true,        // per-task cheapest-capable model mapping
  "currency": "USD",
  "metrics": {
    "transcripts": 7000,                        // volume processed (a full daily batch)
    "transcripts_per_minute": 89.621,           // sustained throughput
    "effective_tokens_per_minute": 1049010.47,  // realized TPM against the quota ceiling
    "p50_latency_ms": 289.432,                  // per-call latency percentiles
    "p95_latency_ms": 462.666,
    "p99_latency_ms": 538.578,
    "total_input_tokens": 78749668,
    "total_output_tokens": 3184683,
    "average_tokens_per_transcript": 11704.91,
    "estimated_cost": 34.717748,                // cost of THIS run (7,000 transcripts)
    "cost_per_transcript": 0.00496,
    "cost_per_1k_transcripts": 4.9597,
    "cost_per_day": 34.72,                      // extrapolated to the daily batch
    "cost_per_month": 1041.53,                  // daily batch × ~30
    "http_429_rate": 0.0014,                    // throttling incidence (0 = no 429s)
    "retry_count": 41,
    "error_count": 0,
    "cache_hit_rate": 0.0,
    "deployment_utilization": { "medium": 0.9283, "small": 1.0 },
    "workload_queue_depth": 41,
    "batch_completion_seconds": 4686.38,        // wall-clock to clear the batch (~1.3 h)
    "throttling_source": "modeled",             // modeled (quota sim) | observed (real 429s)
    "timing_source": "modeled",                 // modeled (quota sim) | observed (wall clock)
    "modeled_http_429_rate": 0.0014,            // quota-simulation values, always present
    "modeled_retry_count": 41,
    "modeled_batch_completion_seconds": 4686.38,
    "observed_attempts": null,                  // observed_* are populated on live runs only
    "observed_http_429_count": null,
    "observed_http_429_rate": null,
    "observed_retry_count": null,
    "observed_transient_error_count": null,
    "observed_backoff_seconds": null,
    "observed_wall_clock_seconds": null,
    "daily_volume": 7000,                       // volume cost/day is scaled to
    "cost_extrapolated": false,                 // true when transcripts != daily_volume
    "cost_extrapolation_factor": 1.0            // daily_volume / transcripts
  },
  "provenance": {
    "generated_at": "2026-09-25T21:12:00+00:00",
    "accelerator_version": "0.1.0",
    "git_commit": "a966aa4…",                   // HEAD at run time
    "git_dirty": false,                         // uncommitted tracked changes present?
    "config_path": "workload-scenarios/post-call-analytics/benchmarks/option-b-azure.yaml",
    "config_sha256": "d87aa5…",                 // hash of the EFFECTIVE config (after overrides)
    "config_overrides": { "execution_mode": "local" },   // what the CLI changed
    "config_execution_mode": "azure",           // what the YAML file declared
    "effective_config": { "...": "..." },       // the full config that actually ran
    "scenario_sha256": "4309ba…",
    "pricing_file": "configs/pricing.example.yaml",
    "pricing_sha256": "35fc83…",
    "deployment_profile": { "deployment_count": 4, "tokens_per_minute_limit": 1000000, "...": "..." },
    "model_deployments": { "medium": "mock:medium", "small": "mock:small" },  // alias -> real target
    "endpoint_host": null,                      // live runs: hostname only, never keys/paths
    "timing_clock": "CLOCK_MONOTONIC_RAW"       // clock behind latency + wall clock (see shared/timing)
  },
  "notes": [
    "Local synthetic run: no Azure calls, mock provider used.",
    "HTTP 429, retries, and batch time are MODELED from the TPM quota simulation.",
    "Caching enabled: prompt, result, metadata."
  ]
}
```

> `execution_backend` records how the calls were made: `local` (offline mock),
> `direct` (live Foundry model inference), `agent` (opt-in Foundry agent), or
> `gateway:<kind>`. A live `--mode azure` run of this config would instead show
> `"execution_mode": "azure"`, `"execution_backend": "direct"`, `observed` sources
> with the `observed_*` fields populated, and `model_deployments` mapping every
> alias to the one `FOUNDRY_MODEL_NAME` deployment.
>
> Results written before `schema_version` 2 have no `provenance`, and their
> 429/retry/batch-time numbers are modeled **even when `execution_mode` is
> `azure`**. The scorecard flags these as legacy; re-run them to get observed
> values.

Compare two results:

```bash
uv run aiwoa report compare \
  --baseline reports/baseline-batch.local.result.json \
  --candidate reports/token-optimization.local.result.json
```

Build a combined operations + cost + quality scorecard across runs (the first
`--run` is the baseline for delta comparison):

```bash
uv run aiwoa report scorecard \
  --run "Current state=reports/current-state-batch.local.result.json::reports/member-id-baseline.eval.json" \
  --run "Optimized target=reports/optimized-target.local.result.json::reports/member-id.eval.json" \
  --output reports/scorecard.json
```

Both `compare` and `scorecard` refuse to run (exit 1) when runs differ from the
baseline in execution mode, backend, 429/timing source, or volume by more than
2x (`--max-volume-ratio`). Re-run them like-for-like, or pass `--allow-mixed` to
render a comparison explicitly labelled as mixed.

Or reproduce the full current-state → optimized story end to end:

```bash
scripts/demo-end-to-end.sh          # fast smoke run
scripts/demo-end-to-end.sh --full   # full 7,000-transcript daily batch (~12h reproduction)
```

Generated JSON files are git-ignored. The thin React UI under `apps/ui/` can load
these files (including `scorecard.json`) for visual comparison.
