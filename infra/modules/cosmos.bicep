// Cosmos DB (serverless) for serving extracted insights (member IDs, sentiment,
// escalation, summaries) to downstream applications — the polyglot serving store.

@description('Azure region for the Cosmos account.')
param location string

@description('Globally-unique Cosmos account name (lowercase).')
param cosmosAccountName string

@description('SQL database name.')
param databaseName string = 'postcall'

@description('Container name for extracted insights.')
param containerName string = 'insights'

@description('Partition key path for the insights container.')
param partitionKeyPath string = '/transcriptId'

@description('Object ID granted the Cosmos DB Built-in Data Contributor role.')
param dataContributorPrincipalId string = ''

@description('Restrict public network access. Set false only for local testing.')
param publicNetworkAccess bool = true

@description('Tags applied to the account.')
param tags object = {}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: cosmosAccountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    disableLocalAuth: true
    publicNetworkAccess: publicNetworkAccess ? 'Enabled' : 'Disabled'
    minimalTlsVersion: 'Tls12'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmos
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: database
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          partitionKeyPath
        ]
        kind: 'Hash'
      }
    }
  }
}

// Cosmos DB Built-in Data Contributor (data-plane) role.
resource dataContributorAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = if (!empty(dataContributorPrincipalId)) {
  parent: cosmos
  name: guid(cosmos.id, dataContributorPrincipalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: dataContributorPrincipalId
    scope: cosmos.id
  }
}

output id string = cosmos.id
output name string = cosmos.name
output endpoint string = cosmos.properties.documentEndpoint
output databaseName string = database.name
output containerName string = container.name
