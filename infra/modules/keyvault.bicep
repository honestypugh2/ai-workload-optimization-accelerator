// Key Vault for connection strings and configuration secrets.
// RBAC authorization model; soft-delete + purge protection for HIPAA posture.

@description('Azure region for the vault.')
param location string

@description('Globally-unique Key Vault name (3-24 chars).')
@minLength(3)
@maxLength(24)
param keyVaultName string

@description('Tenant ID for the vault.')
param tenantId string = subscription().tenantId

@description('Restrict public network access. Set false only for local testing.')
param publicNetworkAccess bool = true

@description('Object ID of the managed identity granted Key Vault Secrets User.')
#disable-next-line secure-secrets-in-params
param secretsUserPrincipalId string = ''

@description('Tags applied to the vault.')
param tags object = {}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: publicNetworkAccess ? 'Enabled' : 'Disabled'
    networkAcls: {
      defaultAction: publicNetworkAccess ? 'Allow' : 'Deny'
      bypass: 'AzureServices'
    }
  }
}

// Key Vault Secrets User role.
var secretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource secretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(secretsUserPrincipalId)) {
  name: guid(keyVault.id, secretsUserPrincipalId, secretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsUserRoleId)
    principalId: secretsUserPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = keyVault.id
output name string = keyVault.name
output uri string = keyVault.properties.vaultUri
