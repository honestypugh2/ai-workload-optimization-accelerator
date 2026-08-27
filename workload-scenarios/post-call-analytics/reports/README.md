# Reports

Benchmark and evaluation results are written here as JSON:

- `*.result.json` — benchmark runs (`aiwoa benchmark run`)
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
│ HTTP 429 rate          │                0.1% │
│ Retries                │                  41 │
│ Cache hit rate         │                0.0% │
│ Queue depth            │                  41 │
└────────────────────────┴─────────────────────┘
Result written to workload-scenarios/post-call-analytics/reports/option-b-azure.result.json
```

The written `*.result.json` (annotated; comments are for docs only — real JSON
has none):

```jsonc
{
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
    "batch_completion_seconds": 4686.38         // modeled wall-clock to clear the batch (~1.3 h)
  },
  "notes": [
    "Local synthetic run: no Azure calls, mock provider used.",
    "Caching enabled: prompt, result, metadata."
  ]
}
```

> `execution_backend` records how the calls were made: `local` (offline mock),
> `direct` (live Foundry model inference), `agent` (opt-in Foundry agent), or
> `gateway:<kind>`. A live `--mode azure` run of this config would instead show
> `"execution_mode": "azure"` and `"execution_backend": "direct"`.

Compare two results:

```bash
uv run aiwoa report compare \
  --baseline reports/baseline-batch.result.json \
  --candidate reports/token-optimization.result.json
```

Build a combined operations + cost + quality scorecard across runs (the first
`--run` is the baseline for delta comparison):

```bash
uv run aiwoa report scorecard \
  --run "Current state=reports/current-state-batch.result.json::reports/member-id-baseline.eval.json" \
  --run "Optimized target=reports/optimized-target.result.json::reports/member-id.eval.json" \
  --output reports/scorecard.json
```

Or reproduce the full current-state → optimized story end to end:

```bash
scripts/demo-end-to-end.sh          # fast smoke run
scripts/demo-end-to-end.sh --full   # full 7,000-transcript daily batch (~12h reproduction)
```

Generated JSON files are git-ignored. The thin React UI under `apps/ui/` can load
these files (including `scorecard.json`) for visual comparison.
