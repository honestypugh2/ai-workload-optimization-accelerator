# Post-Call Analytics workload scenario

First workload plugin for the AI Workload Optimization Accelerator. Emulates the
**Call Center Post-Call Analytics** workload with entirely synthetic
data.

## Layout

| Path | Purpose |
| --- | --- |
| `scenario.yaml` | Scenario definition (model catalog, mappings, deployment + dataset profiles) |
| `configs/` | Pricing and architecture overlays (baseline, optimized, foundry, local) |
| `prompts/` | Baseline, optimized, and member-id extraction prompts |
| `benchmarks/` | Benchmark run definitions mapping to assessment recommendations |
| `evaluations/` | Evaluation definitions with release-gate thresholds |
| `sample-data/` | Synthetic sample transcripts + `dataset-profile.yaml` |
| `reports/` | Generated benchmark/evaluation JSON (git-ignored) |

## Workload profile

- ~7,000 transcripts/day, ~5,000 tokens average input
- Current state: Microsoft Foundry + Azure OpenAI Nano-class, **single deployment
  bottleneck**, shared TPM, batch processing, ~2-day insight lag, HTTP 429 under
  load with retry-with-backoff
- Member-id extraction baseline ~30%, optimized target ≥90%

## Quick start

```bash
# List scenarios
uv run aiwoa scenario list

# Baseline (reference) benchmark — reproduces 429 throttling
uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/baseline-batch.yaml

# Optimized routing benchmark
uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/routing-comparison.yaml

# Member-id evaluation (release gate at 90% recall)
uv run aiwoa evaluate run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/evaluations/member-id.yaml
```
## Full benchmarking guide

See [BENCHMARKS.md](BENCHMARKS.md) for the step-by-step runbook: the option
catalog, execution backends (local / direct / agent / gateway), where results
land, how to build the scorecard, and how to read the numbers into a decision.