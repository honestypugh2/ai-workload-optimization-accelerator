# AI Workload Optimization Accelerator

Reusable accelerator for evaluating and optimizing Azure AI workloads across
**throughput, latency, token usage, cost, quality, reliability, and architecture
patterns**.

This repository supports **Performance Optimization Assessments**. The
first workload scenario is **Call Center Post-Call Analytics**. It is a
modular, plugin-based platform — *not* a single distributable SDK — so new Azure
AI workload scenarios can be added over time.

> All data is **synthetic**. No real PHI, PII, member data, call recordings,
> credentials, or proprietary identifiers are included anywhere in this repo.

## Highlights

- **Runs locally without Azure credentials.** Benchmarks and evaluations use
  synthetic data and a deterministic mock model provider by default.
- **Modular `src/` boundaries** — `benchmarking`, `evaluation`, `optimization`,
  `workloads`, `foundry`, `agents`, `observability`, `storage`, `registry`,
  `shared`, `cli`. There is **no** `src/ai_workload_optimization_accelerator/`
  package.
- **Externalized scenarios** under `workload-scenarios/`.
- **Optimization strategies** for token reduction, chunking, routing, caching,
  deterministic extraction, and PTU simulation — all plugin-registered.
- **Member-id extraction** demonstrating movement from a ~30% naive baseline to a
  ~90% optimized target on synthetic labeled data.
- **Azure-specific code is isolated in adapters**; Foundry and the Microsoft
  Agent Framework are optional dependencies.

## Quick start

```bash
uv sync --extra dev

uv run aiwoa scenario list

# Reference baseline benchmark (reproduces HTTP 429 throttling)
uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/baseline-batch.yaml

# Member-id evaluation with a 90% recall release gate
uv run aiwoa evaluate run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/evaluations/member-id.yaml

# Compare two result files
uv run aiwoa report compare \
  --baseline workload-scenarios/post-call-analytics/reports/baseline-batch.result.json \
  --candidate workload-scenarios/post-call-analytics/reports/routing-comparison.result.json
```

### End-to-end demo: current state → optimized

Reproduce the reference current-state batch (single deployment, ~12-hour window to
process 7,000 transcripts, HTTP 429 throttling), apply the optimization levers,
run the quality evaluations, and render one combined operations + cost + quality
scorecard:

```bash
scripts/demo-end-to-end.sh          # fast smoke run
scripts/demo-end-to-end.sh --full   # full 7,000-transcript daily batch
```

The scorecard puts every run side by side — throughput, latency, 429 rate, cost
per transcript/day/month, and member-ID capture (~30% → ~90%) — with a delta vs
the baseline column:

```bash
uv run aiwoa report scorecard \
  --run "Current state=reports/current-state-batch.result.json::reports/member-id-baseline.eval.json" \
  --run "Optimized target=reports/optimized-target.result.json::reports/member-id.eval.json"
```

## Deploy to your Azure subscription

[`infra/`](infra/) contains parameterized Bicep to stand up the scenario in your
own subscription: Azure AI Foundry with a `gpt-nano` Standard deployment, storage,
managed identity + RBAC, monitoring, and optional Cosmos DB, Redis, an API
Management AI gateway, and Container Apps jobs. Slow/expensive components are
toggle-gated so you can start minimal and add optimization levers as you benchmark
them. See [infra/README.md](infra/README.md).

```bash
az group create -n rg-pcaopt-dev -l eastus2
az deployment group create -g rg-pcaopt-dev -f infra/main.bicep -p infra/main.bicepparam
```

## Architecture

```
src/
  benchmarking/   evaluation/   optimization/   workloads/
  foundry/        agents/       observability/  storage/
  registry/       reporting/    shared/         cli/
workload-scenarios/post-call-analytics/   # externalized scenario content
infra/                                     # deployable Bicep (your subscription)
apps/ui/                                   # thin optional React/Vite UI
```

See [docs/architecture/overview.md](docs/architecture/overview.md) and the ADRs
under [docs/decisions/](docs/decisions/) for the design rationale.

## Optimization patterns modeled

**Token reduction** — prompt/JSON-schema optimization · context minimization ·
transcript preprocessing · summarize-before-analyze · selective &
deterministic-first extraction · dynamic prompt construction.

**Deterministic offload** — deterministic member-id extraction (regex,
normalization, fragment reconstruction) with optional check-digit validation and
NER/LLM fallback seams · keyword intent classification · escalation rule
pre-filter · PII/PHI redaction.

**Caching** — prompt · result · metadata · semantic (near-duplicate) ·
incremental / watermark processing.

**Chunking** — full · fixed · speaker-aware · semantic · hierarchical · map-reduce.

**Model routing** — single · round-robin · weighted · health-aware · quota-aware ·
task-based · fallback · PTU-base-plus-Standard-burst · PTU sizing & cost
simulation · event-driven / near-real-time simulation.

### Limitations (patterns modeled but not fully exercisable locally)

These levers are implemented as plugin primitives/adapters and run in the local
synthetic harness, but their production form depends on Azure services or data
this repo cannot reach:

- **Semantic caching** uses a normalized-text key locally; production would use
  embedding-similarity lookup via APIM/Redis. Gateway policies such as content
  safety, jailbreak filtering, and token-metric emission live in the APIM module
  under [infra/](infra/) and are not simulated by the benchmark harness.
- **Incremental / watermark processing** yields zero in-run skips because each
  benchmark processes net-new synthetic transcripts; the saving materializes
  across re-runs, backfills, and retries.
- **PII/PHI redaction** covers structured identifiers (SSN, card, email, phone)
  via regex; production would use Azure AI Language PII detection for names,
  addresses, and dates.
- **Check-digit validation** ships a Luhn example and is disabled by default —
  the payer's real member-id algorithm is not published, so wire it in before
  enabling.
- **NER and LLM member-id fallbacks** are swappable placeholders; wire a real
  model behind the adapter seams.
- **Deployment sharding (multi-region)** is represented by the multi-deployment
  routers (round-robin/weighted/quota-aware) over aggregate capacity; true
  cross-region placement requires deployed Azure endpoints.


## Development

```bash
make sync       # uv sync --extra dev
make lint       # ruff check
make typecheck  # pyright
make test       # pytest
make benchmark  # baseline benchmark
make evaluate   # member-id evaluation
```

## Security & data handling

- No secrets in code; Foundry credentials come from the environment via
  `DefaultAzureCredential`.
- No hardcoded model versions or prices — both are configuration-driven.
- Synthetic data only. See [SECURITY.md](SECURITY.md) and
  [REUSE_NOTES.md](REUSE_NOTES.md).

## License

[MIT](LICENSE).
