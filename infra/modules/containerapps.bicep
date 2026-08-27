// Container Apps environment + a benchmark/processing Job.
// Mirrors the reference batch orchestration (Container App Jobs) and hosts the
// accelerator runner. A manually-triggered Job runs the benchmark/evaluation
// workload; scale it up later for near-real-time event-driven processing.

@description('Azure region for the environment.')
param location string

@description('Name of the Container Apps managed environment.')
param environmentName string

@description('Name of the processing Job.')
param jobName string

@description('Log Analytics workspace GUID for the environment.')
param logAnalyticsCustomerId string

@description('Log Analytics workspace resource ID (used to read the shared key at deploy time).')
param logAnalyticsWorkspaceId string

@description('Resource ID of the user-assigned managed identity for the job.')
param userAssignedIdentityId string

@description('Container image to run. Defaults to a placeholder; push your runner image and update.')
param containerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('CPU cores for the job container.')
param cpu string = '1.0'

@description('Memory for the job container.')
param memory string = '2Gi'

@description('Environment variables for the runner (name/value pairs).')
param environmentVariables array = []

@description('Tags applied to the resources.')
param tags object = {}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2023-09-01').primarySharedKey
      }
    }
  }
}

resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: jobName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityId}': {}
    }
  }
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 43200
      replicaRetryLimit: 1
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
    }
    template: {
      containers: [
        {
          name: 'runner'
          image: containerImage
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: environmentVariables
        }
      ]
    }
  }
}

output environmentId string = environment.id
output environmentName string = environment.name
output jobName string = job.name
