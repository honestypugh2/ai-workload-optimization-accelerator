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

> [!WARNING]
> **Experimental — not production-ready.** This accelerator is for evaluation,
> benchmarking, and design exploration only. It is **not** hardened for production
> use and ships no production support guarantees. Before deploying anything derived
> from it to production, design against:
>
> - [Microsoft Azure Well-Architected Framework (WAF)](https://learn.microsoft.com/en-us/azure/well-architected/)
> - [Azure security baseline for Azure AI services / Cognitive Services](https://learn.microsoft.com/en-us/security/benchmark/azure/baselines/cognitive-services-security-baseline)
>
> You are responsible for security, compliance (e.g. HIPAA/PHI), reliability, and
> cost review of any production deployment.

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

## Prerequisites

You only need the first two rows to run everything locally. The rest is required
**only** when you want to benchmark against a real Microsoft Foundry deployment.

| Requirement | Needed for | Notes |
|-------------|-----------|-------|
| **Python 3.11+** | Everything | `requires-python = ">=3.11"`. |
| **[uv](https://docs.astral.sh/uv/)** | Everything | Manages the virtualenv and dependencies. Install: `curl -LsSf https://astral.sh/uv/install.sh \| sh` (or `pipx install uv` / `brew install uv`). |
| **Azure CLI (`az`)** | Cloud runs only | Sign-in identity for `DefaultAzureCredential`. Install from the [Azure CLI docs](https://learn.microsoft.com/cli/azure/install-azure-cli). |
| **An Azure subscription + Foundry deployment** | Cloud runs only | Either your own (see [Run against Azure](#run-against-azure)) or an existing Foundry project endpoint + model deployment. |
| **Bicep CLI** | Deploying `infra/` only | Bundled with recent `az`; otherwise `az bicep install`. |

> **No Azure account? You can still run the whole accelerator.** Benchmarks and
> evaluations default to a deterministic **mock** model provider over synthetic
> data, so `local` mode needs no credentials, network, or cost.

## Setup (local, step by step)

```bash
# 1. Clone the repository
git clone https://github.com/honestypugh2/ai-workload-optimization-accelerator.git
cd ai-workload-optimization-accelerator

# 2. Install dependencies into a managed virtualenv (creates .venv)
uv sync --extra dev

# 3. Verify the CLI is wired up — lists available workload scenarios
uv run aiwoa scenario list

# 4. Run the reference baseline benchmark (reproduces HTTP 429 throttling)
uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/baseline-batch.yaml

# 5. Run the member-id evaluation (90% recall release gate)
uv run aiwoa evaluate run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/evaluations/member-id.yaml

# 6. Compare two result files
uv run aiwoa report compare \
  --baseline workload-scenarios/post-call-analytics/reports/baseline-batch.result.json \
  --candidate workload-scenarios/post-call-analytics/reports/routing-comparison.result.json
```

`scripts/bootstrap.sh` runs steps 2–3 for you. Every command is also exposed
through the [`Makefile`](Makefile) (`make sync`, `make benchmark`, `make evaluate`,
`make all`).

## How to use the repo — execution modes

The same benchmark configs run in three modes. Set the mode in the config
(`execution_mode:`) or override it per run with `--mode`:

| Mode | What it does | Credentials | Cost |
|------|--------------|-------------|------|
| `local` *(default)* | Deterministic **mock** provider over synthetic transcripts. Reproducible; used for all the modeled scorecards. | none | none |
| `dry-run` | Validates config, prompts, routing, and cost model **without** calling a model. | none | none |
| `azure` | Real inference against your Foundry `gpt-nano` deployment. Produces live latency/throughput/cost. | `az login` + `.env` | Azure token spend |

```bash
# Same config, different mode + scale, written to an explicit output file
uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/current-state-azure.yaml \
  --mode azure --transcripts 30 --concurrency 24 \
  --output workload-scenarios/post-call-analytics/reports/smoke.result.json
```

Useful `benchmark run` flags: `--mode` (override execution mode), `--transcripts`
(override transcript count for smoke vs full runs), `--concurrency` (parallel
transcripts), `--output` (result JSON path).

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

## Run against Azure

Local mode needs nothing. To produce **live** latency/throughput/cost numbers you
need a Microsoft Foundry model deployment and a signed-in identity. Follow the
three steps below.

The Azure adapters are an optional dependency, so install the `foundry` extra
before running in `azure` mode:

```bash
uv sync --extra dev --extra foundry
```

### 1. Provision infrastructure (optional — skip if you already have a Foundry deployment)

[`infra/`](infra/) contains parameterized Bicep to stand up the scenario in your
own subscription: Microsoft Foundry with a `gpt-nano` Standard deployment, storage,
managed identity + RBAC, and monitoring — plus optional Cosmos DB, Redis, an API
Management AI gateway, and Container Apps jobs. Slow/expensive components are
toggle-gated (default **off**), so you start minimal and add optimization levers as
you benchmark them.

```bash
# Sign in and select the target subscription
az login
az account set --subscription "<your-subscription-id>"

# Create a resource group
az group create -n rg-pcaopt-dev -l eastus2

# Review parameters (workload name, model, region quota) — see infra/main.bicepparam
$EDITOR infra/main.bicepparam

# Preview, then deploy
az deployment group what-if -g rg-pcaopt-dev -f infra/main.bicep -p infra/main.bicepparam
az deployment group create  -g rg-pcaopt-dev -f infra/main.bicep -p infra/main.bicepparam
```

Read the deployment outputs you need for `.env`:

```bash
az deployment group show -g rg-pcaopt-dev -n main --query properties.outputs -o json
```

See [infra/README.md](infra/README.md) for the full component list, toggles, and
the HIPAA/PHI hardening notes.

### 2. Configure credentials (`.env`)

Copy the template and fill in your Foundry endpoint and deployment name. These are
the exact variable names the code reads (see
[src/foundry/projects/settings.py](src/foundry/projects/settings.py)):

```bash
cp .env.example .env
```

```bash
# .env — never commit real values (.env is gitignored)
FOUNDRY_PROJECT_ENDPOINT=https://<your-account>.services.ai.azure.com/api/projects/<your-project>
FOUNDRY_MODEL_NAME=gpt-nano            # the deployment name, e.g. gpt-nano
AZURE_TENANT_ID=<your-tenant-guid>     # pins DefaultAzureCredential to the right tenant
AIWOA_GATEWAY_KIND=direct              # direct model inference (default)
AIWOA_EXECUTION_MODE=azure             # or leave local and use --mode azure per run
```

Authenticate with the identity that has access to the Foundry project (no secrets
in code — `DefaultAzureCredential` uses your signed-in session):

```bash
az login --tenant <your-tenant-guid>
```

### 3. Run a live benchmark

Start with a small smoke run, then scale up:

```bash
# 30-transcript smoke run against the real deployment
uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/current-state-azure.yaml \
  --mode azure --transcripts 30 --concurrency 24 \
  --output workload-scenarios/post-call-analytics/reports/smoke.result.json

# Full daily batch (7,000 transcripts)
uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/current-state-azure.yaml \
  --mode azure \
  --output workload-scenarios/post-call-analytics/reports/current-state.result.json
```

Result JSON and logs land in `workload-scenarios/post-call-analytics/reports/`,
which is **gitignored** — live results and PHI-adjacent data never get committed.

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
