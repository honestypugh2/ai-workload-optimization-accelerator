# Infrastructure (`infra/`)

Deployable Azure infrastructure for running the **Post-Call Analytics** workload
optimization scenario in **your own subscription**. It provisions the reference
current-state footprint (a single `gpt-nano` Standard deployment behind Azure AI
Foundry) plus the building blocks needed to incrementally exercise the
optimization levers from the assessment (multi-backend AI gateway, caching,
polyglot serving, event-driven batch processing).

> No organization names, secrets, or PHI live in these templates. Environment-specific
> values are supplied through [`main.bicepparam`](main.bicepparam).

## What gets deployed

| Component | Module | Purpose | Toggle |
|-----------|--------|---------|--------|
| Log Analytics + App Insights | `modules/monitoring.bicep` | Telemetry for benchmarks, jobs, gateway | always |
| User-assigned managed identity | `modules/identity.bicep` | Secretless access (Entra ID / RBAC) | always |
| Key Vault | `modules/keyvault.bicep` | Config secrets, RBAC auth, purge protection | always |
| Storage (ADLS Gen2) | `modules/storage.bicep` | Transcript landing + result exports | always |
| Microsoft Foundry account + `gpt-nano` deployment | `modules/foundry.bicep` | Model serving core (current-state) | always |
| Cosmos DB (serverless) | `modules/cosmos.bicep` | Insight serving store | `deployCosmos` |
| Azure Cache for Redis | `modules/redis.bicep` | Prompt/result/metadata cache | `deployRedis` |
| API Management (AI gateway) | `modules/apim.bicep` | Multi-backend routing, token limits, caching policies | `deployApim` |
| Container Apps env + Job | `modules/containerapps.bicep` | Batch runner (mirrors current-state orchestration) | `deployContainerApps` |

Slow/expensive resources (APIM, Redis) default to **off** so you can start minimal
and add levers as you benchmark them.

## Deploy

```bash
# 1. Sign in and select your subscription
az login
az account set --subscription "<your-subscription-id>"

# 2. Create a resource group
az group create -n rg-pcaopt-dev -l eastus2

# 3. Review and edit parameters
$EDITOR infra/main.bicepparam    # set workloadName, region-appropriate model, quota

# 4. Preview changes (what-if)
az deployment group what-if -g rg-pcaopt-dev \
  -f infra/main.bicep -p infra/main.bicepparam

# 5. Deploy
az deployment group create -g rg-pcaopt-dev \
  -f infra/main.bicep -p infra/main.bicepparam
```

`azd`-style single-command deploys also work if you wrap this in an `azure.yaml`;
the template is self-contained at resource-group scope.

## After deployment

The deployment emits outputs you can wire into `.env` to run the accelerator in
`AZURE` execution mode against the real `gpt-nano` deployment:

```bash
az deployment group show -g rg-pcaopt-dev -n main \
  --query properties.outputs -o json
```

| Output | Maps to `.env` variable |
|--------|-------------------------|
| `foundryEndpoint` | `FOUNDRY_ENDPOINT` |
| `foundryModelDeployment` | `FOUNDRY_MODEL_DEPLOYMENT` |
| `foundryProjectName` | `FOUNDRY_PROJECT` |
| `managedIdentityClientId` | `AZURE_CLIENT_ID` |
| `appInsightsConnectionString` | `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| `cosmosEndpoint` | `COSMOS_ENDPOINT` |

See [`workload-scenarios/post-call-analytics/configs/foundry.reference.yaml`](../workload-scenarios/post-call-analytics/configs/foundry.reference.yaml)
for the matching Foundry-mode scenario config.

## Adding optimization levers

1. **Multi-backend routing** — set `deployApim = true`, add more `Standard`
   deployments to the Foundry account, then point the accelerator's `quota_aware`
   / `ptu_burst` routers at the gateway.
2. **Caching** — set `deployRedis = true` and enable the `prompt`/`result`/
   `metadata` caches in the benchmark config.
3. **PTU / burst** — size PTU with `aiwoa benchmark run` against
   `benchmarks/ptu-sizing.yaml`, then create a provisioned deployment.
4. **Near-real-time** — scale the Container Apps Job to an event-driven trigger.

## HIPAA / PHI note

For a production PHI posture: set `publicNetworkAccess = false`, add private
endpoints + Private DNS zones for Foundry, Storage, Cosmos, Key Vault, and Redis,
and place APIM/Container Apps in a VNet. Local auth is already disabled on Foundry,
Storage, and Cosmos; all access flows through the managed identity and RBAC.

## Validate locally

```bash
az bicep build --file infra/main.bicep    # compiles clean, no warnings
```
