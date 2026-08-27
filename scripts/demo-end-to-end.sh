#!/usr/bin/env bash
#
# End-to-end demonstration: reproduce the customer current-state batch, apply the
# optimization levers, run quality evaluations, and render a single combined
# operations + cost + quality scorecard.
#
# Usage:
#   scripts/demo-end-to-end.sh            # fast smoke run (small transcript count)
#   scripts/demo-end-to-end.sh --full     # full daily volume (7,000 transcripts)
#
# Everything runs locally against synthetic data — no Azure credentials required.
set -euo pipefail
cd "$(dirname "$0")/.."

SCENARIO="post-call-analytics"
BENCH_DIR="workload-scenarios/${SCENARIO}/benchmarks"
EVAL_DIR="workload-scenarios/${SCENARIO}/evaluations"
REPORTS="workload-scenarios/${SCENARIO}/reports"
mkdir -p "$REPORTS"

# ---- Scale selection -------------------------------------------------------
FULL=0
if [[ "${1:-}" == "--full" ]]; then
  FULL=1
fi

if [[ "$FULL" -eq 1 ]]; then
  TX_ARG=()            # use each config's own transcript_count (7,000)
  echo "==> FULL run: reproducing the 7,000-transcript daily batch (this takes a few minutes)"
else
  TX_ARG=(--transcripts 200)
  echo "==> SMOKE run: 200 transcripts (use --full for the 7,000-transcript batch)"
fi

bench() {
  # bench <config-name>
  uv run aiwoa benchmark run \
    --scenario "$SCENARIO" \
    --config "${BENCH_DIR}/$1.yaml" \
    --output "${REPORTS}/$1.result.json" \
    "${TX_ARG[@]}"
}

evaluate() {
  # evaluate <config-name>  (gate failures do not stop the demo)
  uv run aiwoa evaluate run \
    --scenario "$SCENARIO" \
    --config "${EVAL_DIR}/$1.yaml" \
    --output "${REPORTS}/$1.eval.json" || true
}

echo
echo "############################################################"
echo "# 1. Current state — single deployment, full transcripts   #"
echo "############################################################"
bench current-state-batch

echo
echo "############################################################"
echo "# 2. Optimization levers (each isolates one lever)         #"
echo "############################################################"
bench token-optimization       # Phase 2: token reduction
bench chunking-comparison      # Phase 3: selective chunking
bench routing-comparison       # Phase 4: multi-deployment routing
bench ptu-sizing               # Phase 5: provisioned throughput sizing
bench near-real-time-simulation # Phase 6: event-driven near-real-time

echo
echo "############################################################"
echo "# 3. Optimized end state — all levers stacked              #"
echo "############################################################"
bench optimized-target

echo
echo "############################################################"
echo "# 4. Quality evaluations (member-ID capture: 30% -> 90%)   #"
echo "############################################################"
evaluate member-id-baseline    # naive extractor (~30%)
evaluate member-id             # deterministic hybrid cascade (>=90% gate)

echo
echo "############################################################"
echo "# 5. Combined ops + cost + quality scorecard               #"
echo "############################################################"
uv run aiwoa report scorecard \
  --run "Current state=${REPORTS}/current-state-batch.result.json::${REPORTS}/member-id-baseline.eval.json" \
  --run "Token reduction=${REPORTS}/token-optimization.result.json" \
  --run "Multi-deployment=${REPORTS}/routing-comparison.result.json" \
  --run "Optimized target=${REPORTS}/optimized-target.result.json::${REPORTS}/member-id.eval.json" \
  --output "${REPORTS}/scorecard.json"

echo
echo "==> Scorecard written to ${REPORTS}/scorecard.json"
echo "==> Load any *.result.json / *.eval.json / scorecard.json in apps/ui to explore visually."
