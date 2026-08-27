// User-assigned managed identity.
// Used by Container Apps / Jobs to reach Foundry, Cosmos, Storage, and Key Vault
// without secrets (Entra ID / RBAC, HIPAA-aligned).

@description('Azure region for the identity.')
param location string

@description('Name of the user-assigned managed identity.')
param identityName string

@description('Tags applied to the identity.')
param tags object = {}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

output id string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId
output name string = identity.name
