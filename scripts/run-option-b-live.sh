#!/usr/bin/env bash
#
# Live Option B validation on REAL Azure + assessment scorecard.
#
# Option B (assessment §3.3): event-driven micro-batches with task-based routing
# to the cheapest capable model. This script:
#   1. Reads the Foundry endpoint from the deployed infra (rg-pcaopt-dev).
#   2. Preflights that the model endpoint is reachable over Entra ID (AAD).
#   3. Runs current-state AND Option B LIVE on real Azure at the SAME sample
#      size, so the live scorecard is like-for-like (observed 429s + wall clock).
#   4. Produces the full 7,000-transcript MODELED scorecard comparing
#      current-state vs Options A/B/C locally (no per-call cost).
#
# The two scorecards are kept separate on purpose: modeled and live numbers
# measure different things and `aiwoa report scorecard` refuses to mix them.
#
# Prereqs (provisioned by infra/main.bicep):
#   - Foundry account + gpt-nano deployment in rg-pcaopt-dev.
#   - Your signed-in user holds "Cognitive Services OpenAI User" on the account.
#   - az login to the correct subscription; the 'foundry' extra installed.
#
# Usage:
#   scripts/run-option-b-live.sh                    # live sample = 300 transcripts per config
#   SAMPLE=25  scripts/run-option-b-live.sh          # quick/cheap live proof
#   LIVE_CONFIGS="option-b-azure" scripts/run-option-b-live.sh  # skip the live baseline
#   RG=rg-pcaopt-dev DEPLOYMENT=pcaopt-main scripts/run-option-b-live.sh
set -euo pipefail
cd "$(dirname "$0")/.."

RG="${RG:-rg-pcaopt-dev}"
DEPLOYMENT="${DEPLOYMENT:-pcaopt-main}"
SAMPLE="${SAMPLE:-300}"
LIVE_CONFIGS="${LIVE_CONFIGS:-current-state-azure option-b-azure}"
MODELED_CONFIGS="current-state-azure option-a-azure option-b-azure option-c-azure foundry-current-config-azure"
SCENARIO="post-call-analytics"
BENCH_DIR="workload-scenarios/${SCENARIO}/benchmarks"
REPORTS="workload-scenarios/${SCENARIO}/reports"
SCORECARDS="workload-scenarios/${SCENARIO}/scorecards"
mkdir -p "$REPORTS"

az_out() { az deployment group show -g "$RG" -n "$DEPLOYMENT" \
  --query "properties.outputs.$1.value" -o tsv; }

echo "==> Reading deployment outputs from ${RG}/${DEPLOYMENT}"
export FOUNDRY_PROJECT_ENDPOINT="${FOUNDRY_PROJECT_ENDPOINT:-$(az_out foundryProjectEndpoint)}"
MODEL_DEPLOYMENT="$(az_out foundryModelDeployment)"
ACCOUNT_ENDPOINT="$(az_out foundryEndpoint)"
# The direct provider calls the deployment by name; no APIM in front for Option B.
export FOUNDRY_MODEL_NAME="${FOUNDRY_MODEL_NAME:-$MODEL_DEPLOYMENT}"
export AIWOA_GATEWAY_KIND="${AIWOA_GATEWAY_KIND:-direct}"
echo "    FOUNDRY_PROJECT_ENDPOINT=$FOUNDRY_PROJECT_ENDPOINT"
echo "    FOUNDRY_MODEL_NAME=$FOUNDRY_MODEL_NAME"

echo "==> Ensuring the Azure ('foundry') extra is installed"
uv sync --extra foundry >/dev/null

echo "==> Preflight: is the model endpoint reachable over Entra ID?"
TOKEN="$(az account get-access-token \
  --scope https://cognitiveservices.azure.com/.default --query accessToken -o tsv)"
CODE="$(curl -sS -o /dev/null -w '%{http_code}' \
  -X POST "${ACCOUNT_ENDPOINT%/}/openai/deployments/${MODEL_DEPLOYMENT}/chat/completions?api-version=2024-10-21" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"ping"}],"max_tokens":1}')"
if [[ "$CODE" != "200" ]]; then
  echo "ERROR: endpoint returned HTTP ${CODE}. Check 'az login', the subscription," >&2
  echo "       and that your RBAC role has propagated (can take a minute)." >&2
  exit 1
fi
echo "    OK (HTTP 200)"

echo
echo "############################################################"
echo "# 1/3  LIVE on real Azure (${SAMPLE} transcripts each)"
echo "#      ${LIVE_CONFIGS}"
echo "############################################################"
# Default output: reports/<name>.azure.result.json (observed 429s + wall clock).
for cfg in $LIVE_CONFIGS; do
  echo "--> ${cfg}"
  uv run aiwoa benchmark run \
    --scenario "$SCENARIO" \
    --config "${BENCH_DIR}/${cfg}.yaml" \
    --mode azure \
    --transcripts "$SAMPLE"
done

echo
echo "############################################################"
echo "# 2/3  Full 7,000-transcript batch (modeled) for scorecard #"
echo "############################################################"
# Modeled locally: batch-completion is derived from each config's deployment
# topology (deployment_count / TPM), so no per-call Azure cost at full scale.
# Default output: reports/<name>.local.result.json.
for cfg in $MODELED_CONFIGS; do
  echo "--> ${cfg}"
  uv run aiwoa benchmark run \
    --scenario "$SCENARIO" \
    --config "${BENCH_DIR}/${cfg}.yaml" \
    --mode local
done

echo
echo "############################################################"
echo "# 3/3  Scorecards — modeled (7,000/day) and live (sampled)  #"
echo "############################################################"
echo "--> MODELED: current-state vs Options A/B/C"
uv run aiwoa report scorecard --config "${SCORECARDS}/current-state-vs-options.modeled.yaml"
echo
if [[ " ${LIVE_CONFIGS} " == *" current-state-azure "* && " ${LIVE_CONFIGS} " == *" option-b-azure "* ]]; then
  echo "--> LIVE: current-state vs Option B (${SAMPLE} transcripts each)"
  uv run aiwoa report scorecard --config "${SCORECARDS}/current-state-vs-options.live.yaml"
else
  echo "--> LIVE scorecard skipped: needs both current-state-azure and option-b-azure in LIVE_CONFIGS."
fi

echo
echo "Done."
echo "  Live results    : ${REPORTS}/<config>.azure.result.json"
echo "  Modeled results : ${REPORTS}/<config>.local.result.json"
echo "  Re-run with a larger live sample:  SAMPLE=1000 scripts/run-option-b-live.sh"
