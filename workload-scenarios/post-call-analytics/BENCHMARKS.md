# Benchmarking guide — Post-Call Analytics

A step-by-step runbook for the benchmark **options**, what each step does, where
results land, how to read them, and how to connect the numbers to a decision.

For the scenario overview and layout see [README.md](README.md). For the results
folder conventions see [reports/README.md](reports/README.md).

---

## Mental model: two independent axes

A run is defined by **two** separate choices. Don't conflate them.

| Axis | Chosen by | Values | What it controls |
| --- | --- | --- | --- |
| **Workload / option** | the `--config *.yaml` | current-state, option-a/b/c, foundry-current-config, … | Strategy, routing, caching, quota, volume — *the thing being measured* |
| **Execution backend** | environment / `--mode` | `local`, `direct`, `agent`, `gateway:<kind>` | *How* the model calls are made |

The same option YAML runs against any backend without editing it. This keeps the
workload definition portable and the scorecard comparison honest (identical
workload, only the backend varies).

Every result records which backend produced it in the `execution_backend`
field (provenance), so a report is self-documenting:

- `local` — deterministic offline mock (modeled projection, no network)
- `direct` — live Azure Foundry **model inference** (recommended for throughput/cost)
- `agent` — live Foundry **agent runtime** (opt-in; adds per-call overhead)
- `gateway:litellm` / `gateway:apim` — routed through an OpenAI-compatible gateway

---

## Prerequisites

```bash
# Modeled runs (local) need nothing beyond the base install.
uv sync

# Live Azure runs (direct/agent) need the optional foundry extra + sign-in.
uv sync --extra foundry
az login
```

For live runs, point at the deployed project:

```bash
export FOUNDRY_PROJECT_ENDPOINT="<project data-plane endpoint>"
export FOUNDRY_MODEL_NAME="<your deployment name>"   # e.g. gpt-nano
```

---

## The options catalog

Each `*-azure.yaml` mirrors an assessment recommendation. The `*-batch.yaml` /
local variants are the modeled twins used for fast, offline projections.

| Option (config) | Strategy / routing | Deployments · TPM | Represents |
| --- | --- | --- | --- |
| `current-state-azure` | full transcript · single deployment | 1 · 250K shared | The "before": single throttled deployment |
| `option-a-azure` | full transcript · quota-aware | 4 · 800K | Spread load across deployments (cheapest lever) |
| `option-b-azure` | deterministic-first · task-based + cache + chunking | 4 · 1M | **Recommended**: cheapest capable model per task |
| `option-c-azure` | full transcript · PTU burst | PTU 50 | Reserved throughput for predictable latency |
| `foundry-current-config-azure` | full transcript · single deployment | 1 · 24.438M | The reference's *actual* Foundry deployment today |

`foundry-current-config-azure` matches what the reference sees in the portal
(Global Standard, 24,438,000 TPM / RPM 24,438, DefaultV2 filter), so its numbers
line up with their live environment.

---

## Step 1 — Run a benchmark (modeled, offline)

Start local: fast, deterministic, no Azure needed. Great for iterating.

```bash
uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/option-b-azure.yaml \
  --mode local
```

**What happens at each step:**

1. **Config load** — the YAML is validated at the boundary into a typed config.
2. **Dataset synth** — a seeded synthetic dataset (`seed: 1234`) of
   `transcript_count` transcripts is generated (faithful to the reference's size
   distribution). Deterministic → repeatable numbers.
3. **Provider build** — `--mode local` builds the offline mock provider
   (`execution_backend = local`). No network.
4. **Strategy + routing** — each transcript flows through the strategy
   (e.g. deterministic pre-extraction first), tasks are routed to model tiers,
   caches are consulted, and a quota model applies the TPM ceiling (this is what
   produces modeled throttling / 429s and the batch wall-clock).
5. **Aggregation** — per-transcript outcomes roll up into metrics.
6. **Write** — a JSON result is written to `reports/<name>.<mode>.result.json`
   (for example `option-b-azure.local.result.json`), so a local projection of an
   `*-azure.yaml` config can never be mistaken for a live run. If `--mode`
   overrides the config's `execution_mode`, the CLI warns and the result records
   both in `provenance`.

Use `--transcripts 5` for a smoke run, or omit to use the config's full
`transcript_count` (7,000 = a full daily batch).

---

## Step 2 — Run live on Azure (`direct`, recommended)

Same config, real model calls. Leave the gateway/agent toggles unset for the
recommended direct-inference path.

```bash
uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/option-b-azure.yaml \
  --mode azure --transcripts 300
```

The result records `execution_backend = direct` and is written to
`reports/option-b-azure.azure.result.json`. Under the hood this calls the
deployment's `chat/completions` via the authenticated Foundry OpenAI client, so
usage shows on the **deployment's Monitor** blade in the portal (not the Agents
blade). A convenience wrapper wires the env from infra outputs:
`scripts/run-option-b-live.sh`.

Live runs report **observed** throttling and timing: `http_429_rate`,
`retry_count`, and `batch_completion_seconds` come from the real HTTP 429s the
service returned and the measured wall clock (`throttling_source` /
`timing_source = observed`). The quota simulation's numbers are kept alongside
as `modeled_*` fields for comparison.

> **One deployment in `direct` mode.** Direct inference sends every model alias
> (`small`, `medium`, …) to the single `FOUNDRY_MODEL_NAME` deployment, so a live
> task-based routing run does not actually exercise tiered models.
> `provenance.model_deployments` records this and the run's notes flag it. Use a
> gateway with `AIWOA_GATEWAY_DEPLOYMENTS` to route tiers to distinct deployments.

---

## Step 3 (optional) — Opt-in agent backend

To run the *same* workload through the Foundry agent runtime instead of direct
inference, flip one env var — no YAML change:

```bash
export FOUNDRY_USE_AGENT=1
# optional persona:
export FOUNDRY_AGENT_NAME="pca-agent"
export FOUNDRY_AGENT_INSTRUCTIONS="You are a post-call analytics assistant…"

uv run aiwoa benchmark run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/benchmarks/option-b-azure.yaml \
  --mode azure --transcripts 300 \
  --output workload-scenarios/post-call-analytics/reports/option-b-azure.agent.result.json
```

The result records `execution_backend = agent`. Agent calls carry extra
per-request orchestration (persona + server-side state), so this path is
intentionally **not** recommended for peak throughput — it exists to quantify
that overhead against `direct` on an identical workload.

> Gateway path: set `AIWOA_GATEWAY_KIND=apim` (or `litellm`) plus the
> `AIWOA_GATEWAY_*` vars to route through an OpenAI-compatible gateway; results
> record `execution_backend = gateway:<kind>`.

---

## Step 4 — Where to see results

- **Per-run JSON** — `reports/<name>.<mode>.result.json`. Top-level
  `execution_mode` / `execution_backend`, a `metrics` block (throughput, latency
  percentiles, tokens, cost/day + cost/month, `http_429_rate`, `retry_count`,
  `cache_hit_rate`, `batch_completion_seconds`), and a `provenance` block
  (effective config + SHA-256, CLI overrides, deployment profile, the real
  deployment each model alias hit, pricing file hash, git commit, timestamp).
  `throttling_source` / `timing_source` say whether 429s and batch time are
  `modeled` or `observed`; `cost_extrapolated` / `cost_extrapolation_factor`
  say whether cost/day was scaled up from a smaller sample. See
  [reports/README.md](reports/README.md) for an annotated example.
- **Scorecard JSON** — `reports/scorecard.json` (Step 5): the assessment
  deliverable, all options side by side with deltas vs the baseline, plus each
  column's provenance and any comparability issues.
- **UI** — the thin React app under `apps/ui/` loads these JSON files for a
  visual comparison.
- **Azure portal** (live runs only) — the deployment's **Monitor** blade.
  If it reads zero, check the **date range** first (it must cover the run day)
  and allow for ingestion lag.

---

## Step 5 — Build the scorecard

Two scorecards ship, one per kind of evidence. Keep them separate: modeled and
live numbers measure different things.

| Scorecard | Columns | Inputs |
| --- | --- | --- |
| [`current-state-vs-options.modeled.yaml`](scorecards/current-state-vs-options.modeled.yaml) | current-state, option-a/b/c, foundry-current | `*.local.result.json` at 7,000 transcripts |
| [`current-state-vs-options.live.yaml`](scorecards/current-state-vs-options.live.yaml) | current-state, option-b | `*.azure.result.json` at the same live sample size |

```bash
# Modeled (after `--mode local` runs of each option)
uv run aiwoa report scorecard \
  --config workload-scenarios/post-call-analytics/scorecards/current-state-vs-options.modeled.yaml

# Live (after `--mode azure --transcripts N` runs of current-state and option-b)
uv run aiwoa report scorecard \
  --config workload-scenarios/post-call-analytics/scorecards/current-state-vs-options.live.yaml
```

The first run (`current-state`) is the **baseline**; every other column is shown
as a delta against it. A **Provenance** section at the top of the table shows each
column's mode/backend, transcript count, whether 429s are modeled or observed,
whether cost is extrapolated, and which deployments served it. Point each run's
optional `evaluation:` at a member-id `*.eval.json` to add the quality dimension.

**Comparability guard.** `report scorecard` and `report compare` refuse (exit 1)
when a column differs from the baseline in `execution_mode`,
`execution_backend`, 429/timing source, or transcript volume by more than 2x
(`--max-volume-ratio`). They also print non-blocking caveats: legacy results
without provenance, live results whose 429s were modeled, CLI mode overrides,
extrapolated cost, and single-deployment live routing. Pass `--allow-mixed` to
render anyway; the output is then titled as a mixed comparison and
`scorecard.json` records `"mixed": true`.

Ad-hoc two-way comparison:

```bash
uv run aiwoa report compare \
  --baseline reports/current-state-azure.local.result.json \
  --candidate reports/option-b-azure.local.result.json
```

---

## Step 6 — Read the results, and the "so what"

Modeled full-daily-batch (7,000 transcripts, `--mode local`) numbers from an
earlier run of the modeled scorecard. These are quota-simulation projections,
not live Azure measurements (use the live scorecard for observed numbers).
Prompt and pricing changes since then shift the absolute values, so regenerate
with the Step 5 commands before quoting them:

| Option | Batch time | Throughput | HTTP 429 | Cost / month |
| --- | --- | --- | --- | --- |
| current-state | **12.3 h** | 9.5 tx/min | 2.0 % | $812 |
| option-a (quota-aware) | 2.3 h | 51 tx/min | 0.3 % | **$412** |
| option-b (task routing) | **1.3 h** | 90 tx/min | 0.1 % | $1,042 |
| option-c (PTU burst) | 1.5 h | 79 tx/min | 0.1 % | $1,647 |

**So what — translate the numbers into a decision:**

- **The bottleneck is quota, not the model.** The current single 250K-TPM
  deployment throttles (2 % of calls hit 429) and stretches the daily batch to
  **~12 hours** — the root cause of the reference's ~2-day insight lag.
- **The cheapest lever is spreading load.** Option A (quota-aware across 4
  deployments) alone cuts the batch to **~2.3 h** *and lowers* monthly cost to
  **$412** — faster and cheaper, no model changes.
- **The fastest is smart routing.** Option B (deterministic pre-extraction +
  cheapest-capable model per task + caching) clears the batch in **~1.3 h** with
  429s near zero — the recommended balance of speed and effort.
- **PTU buys predictability, not top speed.** Option C's reserved throughput
  gives steady latency but the highest cost; justify it only when latency SLAs
  demand guaranteed capacity.
- **Ground it in their reality.** `foundry-current-config` reproduces the
  reference's actual 24.438M-TPM Global Standard deployment, so the comparison
  starts from the environment they already see in the portal.

Pair this with the **quality** story (member-id extraction ~30 % → ≥90 % target
via the optimized prompts/evaluation) and the deliverable becomes: *"same
workload, hours instead of days, fewer errors, at equal-or-lower cost — and here
is the evidence."*

---

## Quality dimension (release gate)

```bash
uv run aiwoa evaluate run --scenario post-call-analytics \
  --config workload-scenarios/post-call-analytics/evaluations/member-id.yaml
```

Writes `reports/member-id.eval.json` with recall/precision against a labeled
set and pass/fail against the configured thresholds. Reference it from the
scorecard runs to fuse ops + cost + quality into one view.

---

## Troubleshooting

- **Portal Monitor shows 0** — almost always the **date range** doesn't cover
  the run (or ingestion lag). Widen it to include the run day.
- **Agents blade is empty after a `direct` run** — expected. Direct inference
  registers on the *deployment*, not the Agents blade. Use `FOUNDRY_USE_AGENT=1`
  to exercise the agent path.
- **Transient `404 Project not found` right after deploy** — Foundry project
  eventual consistency. Re-run; the runner aborts on any per-call error.
- **`azure-ai-projects not installed`** — run `uv sync --extra foundry`.
