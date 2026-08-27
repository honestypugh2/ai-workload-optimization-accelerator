#!/usr/bin/env bash
#
# Live Option B validation on REAL Azure + customer scorecard.
#
# Option B (assessment §3.3): event-driven micro-batches with task-based routing
# to the cheapest capable model. This script:
#   1. Reads the Foundry endpoint from the deployed infra (rg-pcaopt-dev).
#   2. Preflights that the model endpoint is reachable over Entra ID (AAD).
#   3. Runs Option B LIVE against real Azure on a small sample (proves it works).
#   4. Produces the full 7,000-transcript scorecard comparing current-state vs
#      Options A/B/C. Batch-completion time is MODELED from each config's quota
#      topology, so the full-scale comparison runs locally (no per-call cost)
#      while step 3 provides the real-Azure proof point.
#
# Prereqs (provisioned by infra/main.bicep):
#   - Foundry account + gpt-nano deployment in rg-pcaopt-dev.
#   - Your signed-in user holds "Cognitive Services OpenAI User" on the account.
#   - az login to the correct subscription; the 'foundry' extra installed.
#
# Usage:
#   scripts/run-option-b-live.sh                    # live sample = 300 transcripts
#   SAMPLE=25  scripts/run-option-b-live.sh          # quick/cheap live proof
#   RG=rg-pcaopt-dev DEPLOYMENT=pcaopt-main scripts/run-option-b-live.sh
set -euo pipefail
cd "$(dirname "$0")/.."

RG="${RG:-rg-pcaopt-dev}"
DEPLOYMENT="${DEPLOYMENT:-pcaopt-main}"
SAMPLE="${SAMPLE:-300}"
SCENARIO="post-call-analytics"
BENCH_DIR="workload-scenarios/${SCENARIO}/benchmarks"
REPORTS="workload-scenarios/${SCENARIO}/reports"
SCORECARD="workload-scenarios/${SCENARIO}/scorecards/current-state-vs-options.yaml"
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
echo "# 1/3  Option B — LIVE on real Azure (${SAMPLE} transcripts) #"
echo "############################################################"
uv run aiwoa benchmark run \
  --scenario "$SCENARIO" \
  --config "${BENCH_DIR}/option-b-azure.yaml" \
  --mode azure \
  --transcripts "$SAMPLE" \
  --output "${REPORTS}/option-b-azure-live.result.json"

echo
echo "############################################################"
echo "# 2/3  Full 7,000-transcript batch (modeled) for scorecard #"
echo "############################################################"
# Modeled locally: batch-completion is derived from each config's deployment
# topology (deployment_count / TPM), so no per-call Azure cost at full scale.
for cfg in current-state-azure option-a-azure option-b-azure option-c-azure; do
  echo "--> ${cfg}"
  uv run aiwoa benchmark run \
    --scenario "$SCENARIO" \
    --config "${BENCH_DIR}/${cfg}.yaml" \
    --mode local \
    --output "${REPORTS}/${cfg}.result.json"
done

echo
echo "############################################################"
echo "# 3/3  Scorecard — current-state vs Options A/B/C          #"
echo "############################################################"
uv run aiwoa report scorecard --config "$SCORECARD"

echo
echo "Done."
echo "  Live Azure proof : ${REPORTS}/option-b-azure-live.result.json"
echo "  Scorecard inputs : ${REPORTS}/{current-state,option-a,option-b,option-c}-azure.result.json"
echo "  Re-run with a larger live sample:  SAMPLE=1000 scripts/run-option-b-live.sh"
