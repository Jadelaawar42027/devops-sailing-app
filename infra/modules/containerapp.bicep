// One Container App: Consumption plan, scales to zero, max 1 replica (brief §4).
@description('Container App name, e.g. sdd-3a-g3-api')
param name string
param location string
param environmentId string
param image string
param env array
param secrets array = []
param registries array = []

@allowed(['Single', 'Multiple'])
param revisionsMode string = 'Single'

@description('Blue-green only: the revision that keeps 100% of traffic while a new one is tested.')
param stableRevision string = ''

var traffic = (revisionsMode == 'Multiple' && !empty(stableRevision))
  ? [{ revisionName: stableRevision, weight: 100, label: 'blue' }]
  : [{ latestRevision: true, weight: 100 }]

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: revisionsMode
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        traffic: traffic
      }
      secrets: secrets
      registries: registries
    }
    template: {
      containers: [
        {
          name: 'app'
          image: image
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: env
          probes: [
            {
              // Startup can take a while: Azure SQL serverless may need ~1 min to resume.
              type: 'Startup'
              httpGet: { path: '/health', port: 8000 }
              periodSeconds: 10
              failureThreshold: 30
            }
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8000 }
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '20' } } }]
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output latestRevision string = app.properties.latestRevisionName
