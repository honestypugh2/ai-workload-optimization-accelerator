// Azure API Management as the AI gateway front door.
// Enables later multi-backend load balancing across model deployments,
// token-limit / semantic-caching / content-safety policies, and per-consumer
// metrics — the gateway optimization lever from the assessment.

@description('Azure region for the APIM instance.')
param location string

@description('Name of the API Management service.')
param apimName string

@description('Publisher email for the APIM instance.')
param publisherEmail string

@description('Publisher organization name.')
param publisherName string

@description('APIM SKU. Developer for dev/test; StandardV2/Premium for production.')
@allowed([
  'Developer'
  'Basic'
  'Standard'
  'StandardV2'
  'Premium'
])
param skuName string = 'Developer'

@description('Number of scale units.')
@minValue(1)
param skuCapacity int = 1

@description('Resource ID of the user-assigned managed identity used to reach backends.')
param userAssignedIdentityId string = ''

@description('Log Analytics workspace ID for diagnostics.')
param logAnalyticsId string = ''

@description('Tags applied to the APIM instance.')
param tags object = {}

resource apim 'Microsoft.ApiManagement/service@2024-05-01' = {
  name: apimName
  location: location
  tags: tags
  sku: {
    name: skuName
    capacity: skuCapacity
  }
  identity: empty(userAssignedIdentityId)
    ? {
        type: 'SystemAssigned'
      }
    : {
        type: 'SystemAssigned, UserAssigned'
        userAssignedIdentities: {
          '${userAssignedIdentityId}': {}
        }
      }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
  }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsId)) {
  name: 'apim-diagnostics'
  scope: apim
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

output id string = apim.id
output name string = apim.name
output gatewayUrl string = apim.properties.gatewayUrl
output principalId string = apim.identity.principalId
