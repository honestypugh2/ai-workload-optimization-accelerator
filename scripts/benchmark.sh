#!/usr/bin/env bash
# Run the offline baseline + token-optimization benchmarks and print a diff.
set -euo pipefail
cd "$(dirname "$0")/.."

SCENARIO="post-call-analytics"
BENCH_DIR="workload-scenarios/${SCENARIO}/benchmarks"

uv run aiwoa benchmark run --scenario "$SCENARIO" --config "${BENCH_DIR}/baseline-batch.yaml"
uv run aiwoa benchmark run --scenario "$SCENARIO" --config "${BENCH_DIR}/token-optimization.yaml"

REPORTS="workload-scenarios/${SCENARIO}/reports"
echo
echo "==> Baseline vs optimized comparison"
uv run aiwoa report compare \
  --baseline "${REPORTS}/baseline-batch.result.json" \
  --candidate "${REPORTS}/token-optimization.result.json"
