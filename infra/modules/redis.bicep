// Azure Cache for Redis — result/prompt/metadata cache backing the accelerator's
// caching optimization lever (prompt, result, metadata, incremental caches).

@description('Azure region for the cache.')
param location string

@description('Name of the Redis cache.')
param redisName string

@description('SKU family: C (Basic/Standard) or P (Premium).')
@allowed([
  'C'
  'P'
])
param skuFamily string = 'C'

@description('SKU name.')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param skuName string = 'Standard'

@description('SKU capacity (0-6 for C, 1-5 for P).')
@minValue(0)
@maxValue(6)
param skuCapacity int = 1

@description('Tags applied to the cache.')
param tags object = {}

resource redis 'Microsoft.Cache/redis@2024-03-01' = {
  name: redisName
  location: location
  tags: tags
  properties: {
    sku: {
      family: skuFamily
      name: skuName
      capacity: skuCapacity
    }
    minimumTlsVersion: '1.2'
    enableNonSslPort: false
    redisConfiguration: {
      'aad-enabled': 'true'
    }
  }
}

output id string = redis.id
output name string = redis.name
output hostName string = redis.properties.hostName
output sslPort int = redis.properties.sslPort
