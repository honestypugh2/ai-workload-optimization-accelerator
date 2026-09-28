#!/usr/bin/env bash
#
# Regenerate the synthetic result sets bundled with the viewer (apps/ui/public/samples).
# The viewer opens the first set in samples/index.json on start.
#
# Everything runs locally with the mock provider — no Azure credentials, no customer data.
# Run from a clean checkout so every result records git_dirty=false.
#
# Only the synthetic sets are regenerated. The live-* sets are copies of past live Azure
# runs (no endpoints or credentials) and are left untouched; their takeaways and observed
# figures live in samples/index.json.
#
# Usage:
#   scripts/refresh-ui-samples.sh
set -euo pipefail
cd "$(dirname "$0")/.."

SCENARIO="post-call-analytics"
BENCH="workload-scenarios/${SCENARIO}/benchmarks"
EVALS="workload-scenarios/${SCENARIO}/evaluations"
SAMPLES="apps/ui/public/samples"

bench() {
  # bench <out-dir> <config-name> <transcripts>
  uv run aiwoa benchmark run --scenario "$SCENARIO" --config "${BENCH}/$2.yaml" \
    --mode local --transcripts "$3" --output "$1/$2.local.result.json"
}

evaluate() {
  # evaluate <out-dir> <config-name>  (the naive baseline has no gate to pass)
  uv run aiwoa evaluate run --scenario "$SCENARIO" --config "${EVALS}/$2.yaml" \
    --output "$1/$2.eval.json" || true
}

echo "==> Reference demo: current state -> optimized (200 transcripts)"
DEMO="${SAMPLES}/reference-demo"
rm -rf "$DEMO" && mkdir -p "$DEMO"
for cfg in current-state-batch token-optimization routing-comparison optimized-target; do
  bench "$DEMO" "$cfg" 200
done
evaluate "$DEMO" member-id-baseline
evaluate "$DEMO" member-id
uv run aiwoa report scorecard \
  --run "Current state=${DEMO}/current-state-batch.local.result.json::${DEMO}/member-id-baseline.eval.json" \
  --run "Token reduction=${DEMO}/token-optimization.local.result.json" \
  --run "Multi-deployment=${DEMO}/routing-comparison.local.result.json" \
  --run "Optimized target=${DEMO}/optimized-target.local.result.json::${DEMO}/member-id.eval.json" \
  --output "${DEMO}/scorecard.json"

echo "==> Architecture options: current state vs Options A/B/C (modeled, 7,000/day)"
OPTS="${SAMPLES}/architecture-options"
rm -rf "$OPTS" && mkdir -p "$OPTS"
for cfg in current-state-azure option-a-azure option-b-azure option-c-azure foundry-current-config-azure; do
  bench "$OPTS" "$cfg" 7000
done
uv run aiwoa report scorecard \
  --run "Current state=${OPTS}/current-state-azure.local.result.json" \
  --run "Option A=${OPTS}/option-a-azure.local.result.json" \
  --run "Option B=${OPTS}/option-b-azure.local.result.json" \
  --run "Option C=${OPTS}/option-c-azure.local.result.json" \
  --run "High-quota single deployment=${OPTS}/foundry-current-config-azure.local.result.json" \
  --output "${OPTS}/scorecard.json"

echo "==> Samples written to ${SAMPLES} (index: ${SAMPLES}/index.json)"
