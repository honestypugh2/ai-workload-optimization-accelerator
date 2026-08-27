// Microsoft Foundry (AI Services) account + Foundry project + a model deployment.
// This is the model-serving core: the "gpt-nano" Standard deployment is the
// reference current-state starting point. Additional deployments can be added
// later to exercise multi-backend routing and PTU/burst optimization.

@description('Azure region for the Foundry account.')
param location string

@description('Name of the Microsoft Foundry (AI Services) account.')
param foundryAccountName string

@description('Custom subdomain for the account (defaults to the account name).')
param customSubDomainName string = foundryAccountName

@description('Create a Foundry project under the account.')
param deployProject bool = true

@description('Name of the Foundry project.')
param projectName string = '${foundryAccountName}-proj'

@description('Restrict public network access. Set false only for local testing.')
param publicNetworkAccess bool = true

@description('Model deployment name (the alias the app/gateway calls).')
param modelDeploymentName string = 'gpt-nano'

@description('Underlying model format.')
param modelFormat string = 'OpenAI'

@description('Underlying model name (e.g. a nano-class model). Parameterized, never hardcoded in app code.')
param modelName string = 'gpt-4.1-nano'

@description('Underlying model version.')
param modelVersion string = '2025-04-14'

@description('Deployment SKU name. Standard for PayGo; provision PTU separately later.')
param modelSkuName string = 'Standard'

@description('Deployment capacity in thousands of TPM (Standard) or PTU units.')
@minValue(1)
param modelCapacity int = 250

@description('Object ID granted Cognitive Services OpenAI User.')
param openAiUserPrincipalId string = ''

@description('Log Analytics workspace ID for diagnostics.')
param logAnalyticsId string = ''

@description('Tags applied to the account.')
param tags object = {}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: foundryAccountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: customSubDomainName
    allowProjectManagement: true
    publicNetworkAccess: publicNetworkAccess ? 'Enabled' : 'Disabled'
    disableLocalAuth: true
    networkAcls: {
      defaultAction: publicNetworkAccess ? 'Allow' : 'Deny'
    }
  }
}

// The current-state model deployment. capacity models TPM (in thousands) headroom.
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: foundry
  name: modelDeploymentName
  sku: {
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: modelFormat
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = if (deployProject) {
  parent: foundry
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: projectName
    description: 'Post-call analytics workload optimization project.'
  }
}

// Cognitive Services OpenAI User role.
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource openAiUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(openAiUserPrincipalId)) {
  name: guid(foundry.id, openAiUserPrincipalId, openAiUserRoleId)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
    principalId: openAiUserPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsId)) {
  name: 'foundry-diagnostics'
  scope: foundry
  properties: {
    workspaceId: logAnalyticsId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

output accountId string = foundry.id
output accountName string = foundry.name
output endpoint string = foundry.properties.endpoint
output modelDeploymentName string = modelDeployment.name
output projectName string = deployProject ? project.name : ''
// AIProjectClient endpoint (data-plane) — set as FOUNDRY_PROJECT_ENDPOINT.
output projectEndpoint string = deployProject
  ? 'https://${customSubDomainName}.services.ai.azure.com/api/projects/${projectName}'
  : ''
