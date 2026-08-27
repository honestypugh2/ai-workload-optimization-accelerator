#!/usr/bin/env bash
# Run the member-id extraction evaluation gate on synthetic labeled data.
set -euo pipefail
cd "$(dirname "$0")/.."

SCENARIO="post-call-analytics"
EVAL_DIR="workload-scenarios/${SCENARIO}/evaluations"

echo "==> Optimized (deterministic) — 90% recall gate"
uv run aiwoa evaluate run --scenario "$SCENARIO" --config "${EVAL_DIR}/member-id.yaml"

echo
echo "==> Baseline (naive) — demonstrates the ~30% starting point"
uv run aiwoa evaluate run --scenario "$SCENARIO" --config "${EVAL_DIR}/regression.yaml"
