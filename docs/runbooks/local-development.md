# Runbook: Local Development

No Azure credentials are required. Everything runs against a deterministic mock
provider.

## Setup

```bash
uv sync --extra dev
```

## Discover the scenario

```bash
uv run aiwoa scenario list
uv run aiwoa scenario show post-call-analytics
```

## Run a benchmark

```bash
uv run aiwoa benchmark run \
  workload-scenarios/post-call-analytics/benchmarks/baseline-batch.yaml
# writes <name>.result.json under the scenario's reports/ folder
```

## Compare baseline vs optimized

```bash
./scripts/benchmark.sh
# runs baseline + token-optimization, then `aiwoa report compare`
```

## Run an evaluation (with release gate)

```bash
uv run aiwoa evaluate run \
  workload-scenarios/post-call-analytics/evaluations/member-id.yaml
# exits non-zero (2) if a threshold gate fails
```

## Quality gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

## View results (optional UI)

```bash
cd apps/ui
npm install
npm run dev
# open the printed URL, then load *.result.json / *.eval.json files
```

## Expected reference numbers

- Member-ID extraction: naive ≈ 30.8%, deterministic ≈ 93.5% recall.
- Token optimization: ~29k → ~16.6k tokens/transcript window; monthly cost
  ~$968 → ~$573 (mock pricing).

These are produced by the mock provider and are deterministic across runs.
