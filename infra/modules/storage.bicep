// Storage account with ADLS Gen2 (hierarchical namespace) for transcript landing,
// intermediate artifacts, and benchmark/evaluation result exports.

@description('Azure region for the storage account.')
param location string

@description('Globally-unique storage account name (3-24 lowercase alphanumerics).')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Enable ADLS Gen2 hierarchical namespace.')
param enableHierarchicalNamespace bool = true

@description('Blob containers to create.')
param containers array = [
  'transcripts-raw'
  'transcripts-processed'
  'benchmark-results'
  'evaluation-results'
]

@description('Object ID of the managed identity granted Storage Blob Data Contributor.')
param blobContributorPrincipalId string = ''

@description('Tags applied to the storage account.')
param tags object = {}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_ZRS'
  }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: enableHierarchicalNamespace
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    supportsHttpsTrafficOnly: true
    encryption: {
      services: {
        blob: {
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource blobContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [
  for name in containers: {
    parent: blobService
    name: name
    properties: {
      publicAccess: 'None'
    }
  }
]

// Storage Blob Data Contributor role.
var blobContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource blobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(blobContributorPrincipalId)) {
  name: guid(storage.id, blobContributorPrincipalId, blobContributorRoleId)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributorRoleId)
    principalId: blobContributorPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = storage.id
output name string = storage.name
output blobEndpoint string = storage.properties.primaryEndpoints.blob
