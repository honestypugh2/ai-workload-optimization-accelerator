// AI Workload Optimization Accelerator — Post-Call Analytics infrastructure.
//
// Deploys the Azure footprint needed to reproduce the customer current-state
// (single "gpt-nano" Standard deployment, batch processing) and to incrementally
// exercise the optimization levers (multi-backend gateway, caching, polyglot
// serving, event-driven processing). All customer-specific values live in the
// parameter file — this template contains no customer names.
//
// Scope: resource group. Create the group first, then:
//   az deployment group create -g <rg> -f infra/main.bicep -p infra/main.bicepparam

targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Short environment/workload name used to derive resource names (2-12 lowercase alphanumerics).')
@minLength(2)
@maxLength(12)
param workloadName string = 'pcaopt'

@description('Deployment environment tag (e.g. dev, test, prod).')
param environmentTag string = 'dev'

@description('Restrict public network access on data/model services (recommended for PHI/HIPAA).')
param publicNetworkAccess bool = true

// ----- Optional / cost-gated components -----
@description('Deploy Azure API Management as the AI gateway (slow to provision).')
param deployApim bool = false

@description('Deploy Cosmos DB serving store.')
param deployCosmos bool = true

@description('Deploy Azure Cache for Redis.')
param deployRedis bool = false

@description('Deploy Container Apps environment + processing Job.')
param deployContainerApps bool = true

// ----- Foundry / model -----
@description('Model deployment alias the app/gateway calls.')
param modelDeploymentName string = 'gpt-nano'

@description('Underlying model name (parameterized, never hardcoded in app code).')
param modelName string = 'gpt-4.1-nano'

@description('Underlying model version.')
param modelVersion string = '2025-04-14'

@description('Model deployment capacity (thousands of TPM for Standard/GlobalStandard).')
param modelCapacity int = 250

@description('Model deployment SKU. Many subscriptions have zero regional Standard quota for nano-class models; GlobalStandard is the broadly-available default. Use Standard only where you hold regional quota (e.g. data-residency/PHI).')
@allowed([
  'Standard'
  'GlobalStandard'
  'DataZoneStandard'
])
param modelSkuName string = 'GlobalStandard'

// ----- APIM publisher metadata (required only when deployApim = true) -----
@description('APIM publisher email.')
param apimPublisherEmail string = 'admin@example.com'

@description('APIM publisher organization name.')
param apimPublisherName string = 'AI Workload Optimization'

var tags = {
  workload: workloadName
  environment: environmentTag
  solution: 'ai-workload-optimization-accelerator'
  scenario: 'post-call-analytics'
}

var suffix = uniqueString(resourceGroup().id, workloadName)
var namePrefix = '${workloadName}-${environmentTag}'
// Storage/Cosmos/KeyVault need short, restricted names.
var compactName = toLower(replace('${workloadName}${environmentTag}', '-', ''))

// ----- Observability -----
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    logAnalyticsName: '${namePrefix}-log'
    appInsightsName: '${namePrefix}-appi'
    tags: tags
  }
}

// ----- Managed identity -----
module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    identityName: '${namePrefix}-mi'
    tags: tags
  }
}

// ----- Key Vault -----
module keyvault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    location: location
    keyVaultName: take('${compactName}kv${suffix}', 24)
    publicNetworkAccess: publicNetworkAccess
    secretsUserPrincipalId: identity.outputs.principalId
    tags: tags
  }
}

// ----- Storage (ADLS Gen2) -----
module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    storageAccountName: take('${compactName}st${suffix}', 24)
    blobContributorPrincipalId: identity.outputs.principalId
    tags: tags
  }
}

// ----- Foundry account + gpt-nano deployment -----
module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  params: {
    location: location
    foundryAccountName: '${namePrefix}-aifoundry'
    publicNetworkAccess: publicNetworkAccess
    modelDeploymentName: modelDeploymentName
    modelName: modelName
    modelVersion: modelVersion
    modelCapacity: modelCapacity
    modelSkuName: modelSkuName
    openAiUserPrincipalId: identity.outputs.principalId
    logAnalyticsId: monitoring.outputs.logAnalyticsId
    tags: tags
  }
}

// ----- Cosmos DB (optional) -----
module cosmos 'modules/cosmos.bicep' = if (deployCosmos) {
  name: 'cosmos'
  params: {
    location: location
    cosmosAccountName: take('${compactName}cos${suffix}', 44)
    dataContributorPrincipalId: identity.outputs.principalId
    publicNetworkAccess: publicNetworkAccess
    tags: tags
  }
}

// ----- Redis (optional) -----
module redis 'modules/redis.bicep' = if (deployRedis) {
  name: 'redis'
  params: {
    location: location
    redisName: '${namePrefix}-redis'
    tags: tags
  }
}

// ----- APIM AI gateway (optional) -----
module apim 'modules/apim.bicep' = if (deployApim) {
  name: 'apim'
  params: {
    location: location
    apimName: '${namePrefix}-apim'
    publisherEmail: apimPublisherEmail
    publisherName: apimPublisherName
    userAssignedIdentityId: identity.outputs.id
    logAnalyticsId: monitoring.outputs.logAnalyticsId
    tags: tags
  }
}

// ----- Container Apps environment + Job (optional) -----
module containerApps 'modules/containerapps.bicep' = if (deployContainerApps) {
  name: 'containerApps'
  params: {
    location: location
    environmentName: '${namePrefix}-cae'
    jobName: '${namePrefix}-runner'
    logAnalyticsCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsId
    userAssignedIdentityId: identity.outputs.id
    environmentVariables: [
      {
        name: 'AIWOA_EXECUTION_MODE'
        value: 'azure'
      }
      {
        name: 'AZURE_CLIENT_ID'
        value: identity.outputs.clientId
      }
      {
        name: 'FOUNDRY_ENDPOINT'
        value: foundry.outputs.endpoint
      }
      {
        name: 'FOUNDRY_MODEL_DEPLOYMENT'
        value: foundry.outputs.modelDeploymentName
      }
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        value: monitoring.outputs.appInsightsConnectionString
      }
    ]
    tags: tags
  }
}

// ----- Outputs (wire these into .env for AZURE execution mode) -----
output location string = location
output managedIdentityClientId string = identity.outputs.clientId
output foundryEndpoint string = foundry.outputs.endpoint
output foundryProjectEndpoint string = foundry.outputs.projectEndpoint
output foundryModelDeployment string = foundry.outputs.modelDeploymentName
output foundryProjectName string = foundry.outputs.projectName
output keyVaultUri string = keyvault.outputs.uri
output storageBlobEndpoint string = storage.outputs.blobEndpoint
output appInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
#disable-next-line BCP318
output cosmosEndpoint string = deployCosmos ? cosmos.outputs.endpoint : ''
#disable-next-line BCP318
output redisHostName string = deployRedis ? redis.outputs.hostName : ''
#disable-next-line BCP318
output apimGatewayUrl string = deployApim ? apim.outputs.gatewayUrl : ''
#disable-next-line BCP318
output containerJobName string = deployContainerApps ? containerApps.outputs.jobName : ''
