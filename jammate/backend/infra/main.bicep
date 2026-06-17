// JamMate — Infrastructure as Code (Bicep), scope = resource group.
// Provisiona tutto il backend su Azure in regione UE:
//   PostgreSQL Flexible Server + DB · Function App (Node 20, Consumption) +
//   Storage + Application Insights · Key Vault (RBAC) con la connection string,
//   letta dalla Function App via Managed Identity.
// Deploy: vedi infra/deploy.sh (un comando). Niente segreti nel codice.

@description('Prefisso nomi risorse (es. "jammate"). I nomi globali avranno un suffisso univoco.')
param namePrefix string = 'jammate'

@description('Regione (UE consigliata).')
param location string = 'westeurope'

@description('Utente amministratore PostgreSQL.')
param pgAdminUser string = 'jammate_admin'

@secure()
@description('Password amministratore PostgreSQL (forte).')
param pgAdminPassword string

@description('Application (client) ID dell\'app Entra External ID.')
param entraAudience string = ''
@description('Issuer del token Entra (es. https://<tenant>.ciamlogin.com/<tenant-id>/v2.0).')
param entraIssuer string = ''
@description('JWKS URI di Entra.')
param entraJwksUri string = ''

var suffix = uniqueString(resourceGroup().id)
var pgServerName = '${namePrefix}-db-${suffix}'
var dbName = 'jammate'
var funcAppName = '${namePrefix}-api-${suffix}'
var planName = '${namePrefix}-plan'
var storageName = toLower(take('${namePrefix}st${suffix}', 24))
var kvName = take('kv-${namePrefix}-${suffix}', 24)
var laName = '${namePrefix}-logs'
var aiName = '${namePrefix}-insights'
var contentShare = toLower('${namePrefix}-content')
var pgConnString = 'postgres://${pgAdminUser}:${pgAdminPassword}@${pgServerName}.postgres.database.azure.com:5432/${dbName}?sslmode=require'
// Ruolo "Key Vault Secrets User"
var kvSecretsUserRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

// ---------- Osservabilità ----------
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: laName
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: aiName
  location: location
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: logs.id }
}

// ---------- Storage per la Function App ----------
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { minimumTlsVersion: 'TLS1_2', allowBlobPublicAccess: false }
}
var storageConn = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storage.listKeys().keys[0].value}'

// ---------- Database PostgreSQL Flexible (Burstable, economico) ----------
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: pgServerName
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: pgAdminUser
    administratorLoginPassword: pgAdminPassword
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
  }
}

resource pgDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: pg
  name: dbName
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

// Consente l'accesso dai servizi Azure (Function App) e — temporaneamente — il
// caricamento dello schema. Per il caricamento dal PC, deploy.sh aggiunge il tuo IP.
resource pgAllowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: pg
  name: 'AllowAllAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

// ---------- Key Vault (RBAC) ----------
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: kvName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: tenant().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
  }
}

resource pgSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'PG-CONNECTION-STRING'
  properties: { value: pgConnString }
}

// ---------- Piano + Function App ----------
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' }
  kind: 'linux'
  properties: { reserved: true }
}

resource func 'Microsoft.Web/sites@2023-12-01' = {
  name: funcAppName
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'NODE|20'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      cors: { allowedOrigins: [ 'https://claus1982.github.io' ] }
      appSettings: [
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'node' }
        { name: 'WEBSITE_NODE_DEFAULT_VERSION', value: '~20' }
        { name: 'AzureWebJobsStorage', value: storageConn }
        { name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING', value: storageConn }
        { name: 'WEBSITE_CONTENTSHARE', value: contentShare }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'PG_CONNECTION_STRING', value: '@Microsoft.KeyVault(SecretUri=${kv.properties.vaultUri}secrets/PG-CONNECTION-STRING/)' }
        { name: 'ENTRA_AUDIENCE', value: entraAudience }
        { name: 'ENTRA_ISSUER', value: entraIssuer }
        { name: 'ENTRA_JWKS_URI', value: entraJwksUri }
      ]
    }
  }
}

// La Function App (Managed Identity) può leggere i segreti dal Key Vault.
resource kvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, func.id, kvSecretsUserRoleId)
  properties: {
    roleDefinitionId: kvSecretsUserRoleId
    principalId: func.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output functionAppName string = func.name
output functionAppUrl string = 'https://${func.properties.defaultHostName}'
output pgServerFqdn string = '${pgServerName}.postgres.database.azure.com'
output pgAdminUser string = pgAdminUser
output databaseName string = dbName
output keyVaultName string = kv.name
