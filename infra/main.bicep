// All Azure resources of the group, in the existing resource group rg-sdd-<class>-g<N> (brief §4).
// Applied by the CD pipeline on every merge to main, so nothing is changed by hand.
//   2 Container Apps, 2 serverless SQL databases (one per service), 1 Static Web App,
//   plus what they need: the Container Apps environment, its Log Analytics workspace, a SQL server.
targetScope = 'resourceGroup'

@description('Group prefix, e.g. sdd-3a-g3. Every resource name starts with it.')
param prefix string

param location string = resourceGroup().location

@description('Static Web Apps is only offered in a few regions.')
param uiLocation string = 'westeurope'

@description('Full image references, e.g. ghcr.io/org/repo/api:<sha>')
param apiImage string
param forecastImage string

@description('Shown by /health; the CD pipeline passes the commit SHA.')
param appVersion string = 'manual'

param sqlAdminLogin string = 'sailingadmin'

@secure()
@description('From the GitHub secret SQL_ADMIN_PASSWORD. Never stored in the repository.')
param sqlAdminPassword string

@description('Only needed if the GHCR packages are private.')
param ghcrUsername string = ''
@secure()
param ghcrToken string = ''

@allowed(['Single', 'Multiple'])
@description('Multiple = blue-green (scripts/bluegreen.sh). Single = replace the revision in place.')
param revisionsMode string = 'Single'
param apiStableRevision string = ''
param forecastStableRevision string = ''

// ---------- Monitoring: Log Analytics workspace of the Container Apps environment (§4, §6)

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: 1 } // keeps a runaway log loop from costing money
  }
}

// The dashboard and SLO queries, deployed as saved searches (single source: docs/monitoring/queries).
var savedQueries = [
  { id: 'request-count', name: 'Request count', query: loadTextContent('../docs/monitoring/queries/request-count.kql') }
  { id: 'error-rate', name: 'Error rate', query: loadTextContent('../docs/monitoring/queries/error-rate.kql') }
  { id: 'response-time', name: 'Response time', query: loadTextContent('../docs/monitoring/queries/response-time.kql') }
  { id: 'slo-windows', name: 'SLO - windows', query: loadTextContent('../docs/monitoring/queries/slo-windows.kql') }
  { id: 'slo-windows-trend', name: 'SLO - windows trend', query: loadTextContent('../docs/monitoring/queries/slo-windows-trend.kql') }
  { id: 'upstream-health', name: 'Upstream health', query: loadTextContent('../docs/monitoring/queries/upstream-health.kql') }
  { id: 'top-routes', name: 'Top routes', query: loadTextContent('../docs/monitoring/queries/top-routes.kql') }
  { id: 'recent-errors', name: 'Recent errors', query: loadTextContent('../docs/monitoring/queries/recent-errors.kql') }
]

resource searches 'Microsoft.OperationalInsights/workspaces/savedSearches@2020-08-01' = [
  for q in savedQueries: {
    parent: logs
    name: 'sailing-${q.id}'
    properties: {
      category: 'Sailing planner'
      displayName: q.name
      query: q.query
      version: 2
    }
  }
]

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// ---------- Data: one serverless database per service, auto-pause after 1 h (§3a, §4)

resource sql 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: '${prefix}-sql'
  location: location
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

// Container Apps (Consumption) have no fixed outbound IP: allow Azure services only.
resource allowAzure 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sql
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

var databaseNames = { api: '${prefix}-api-db', forecast: '${prefix}-forecast-db' }

resource databases 'Microsoft.Sql/servers/databases@2023-08-01-preview' = [
  for db in items(databaseNames): {
    parent: sql
    name: db.value
    location: location
    sku: { name: 'GP_S_Gen5', tier: 'GeneralPurpose', family: 'Gen5', capacity: 1 }
    properties: {
      autoPauseDelay: 60
      minCapacity: json('0.5')
      zoneRedundant: false
      requestedBackupStorageRedundancy: 'Local'
    }
  }
]

// ---------- UI: one Static Web App per group (§4)

resource ui 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${prefix}-ui'
  location: uiLocation
  sku: { name: 'Free', tier: 'Free' }
  properties: {}
}

// ---------- The two services

var registries = empty(ghcrToken) ? [] : [
  { server: 'ghcr.io', username: ghcrUsername, passwordSecretRef: 'ghcr-token' }
]
var registrySecrets = empty(ghcrToken) ? [] : [{ name: 'ghcr-token', value: ghcrToken }]
var secrets = concat([{ name: 'db-password', value: sqlAdminPassword }], registrySecrets)

func commonEnv(version string, origin string, dbHost string, dbName string, dbUser string) array => [
  { name: 'APP_VERSION', value: version }
  { name: 'LOG_LEVEL', value: 'INFO' }
  { name: 'CORS_ORIGINS', value: origin }
  { name: 'DB_HOST', value: dbHost }
  { name: 'DB_NAME', value: dbName }
  { name: 'DB_USER', value: dbUser }
  { name: 'DB_PASSWORD', secretRef: 'db-password' }
]

var uiOrigin = 'https://${ui.properties.defaultHostname}'

module forecastApp 'modules/containerapp.bicep' = {
  name: 'forecast-app'
  dependsOn: [databases]
  params: {
    name: '${prefix}-forecast'
    location: location
    environmentId: environment.id
    image: forecastImage
    secrets: secrets
    registries: registries
    revisionsMode: revisionsMode
    stableRevision: forecastStableRevision
    env: commonEnv(appVersion, uiOrigin, sql.properties.fullyQualifiedDomainName, databaseNames.forecast, sqlAdminLogin)
  }
}

module apiApp 'modules/containerapp.bicep' = {
  name: 'api-app'
  dependsOn: [databases]
  params: {
    name: '${prefix}-api'
    location: location
    environmentId: environment.id
    image: apiImage
    secrets: secrets
    registries: registries
    revisionsMode: revisionsMode
    stableRevision: apiStableRevision
    env: concat(
      commonEnv(appVersion, uiOrigin, sql.properties.fullyQualifiedDomainName, databaseNames.api, sqlAdminLogin),
      [{ name: 'FORECAST_URL', value: 'https://${forecastApp.outputs.fqdn}' }]
    )
  }
}

output apiUrl string = 'https://${apiApp.outputs.fqdn}'
output forecastUrl string = 'https://${forecastApp.outputs.fqdn}'
output uiUrl string = uiOrigin
output apiLatestRevision string = apiApp.outputs.latestRevision
output forecastLatestRevision string = forecastApp.outputs.latestRevision
output logAnalyticsWorkspace string = logs.name
