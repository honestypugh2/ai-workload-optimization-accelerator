using './main.bicep'

// ---------------------------------------------------------------------------
// Parameters for deploying into YOUR Azure subscription.
// No secrets or customer names belong in this file. Replace placeholders and
// deploy with:
//   az group create -n <rg> -l <region>
//   az deployment group create -g <rg> -f infra/main.bicep -p infra/main.bicepparam
// ---------------------------------------------------------------------------

// Short workload name used to derive resource names (2-12 lowercase alphanumerics).
param workloadName = 'pcaopt'
param environmentTag = 'dev'

// Keep public access on for an initial test; set false and add private endpoints
// for a PHI/HIPAA-aligned posture.
param publicNetworkAccess = true

// Start minimal for a live Option-B benchmark run from the CLI: Foundry + model +
// monitoring + identity + key vault + storage. Cosmos/Container Apps/APIM are not
// needed to produce the scorecard (batch-completion time is modeled from the
// benchmark config), so leave them off to keep cost and provisioning time low.
param deployApim = false
param deployCosmos = false
param deployRedis = false
param deployContainerApps = false

// The current-state "gpt-nano" deployment. Adjust modelName/version to a
// nano-class model available in your region and modelCapacity to your quota.
// Regional Standard quota for nano models is frequently 0; GlobalStandard is the
// portable default. Switch to Standard only where you hold regional quota.
param modelDeploymentName = 'gpt-nano'
param modelName = 'gpt-4.1-nano'
param modelVersion = '2025-04-14'
param modelCapacity = 250
param modelSkuName = 'GlobalStandard'

// Only used when deployApim = true.
param apimPublisherEmail = 'admin@example.com'
param apimPublisherName = 'AI Workload Optimization'
