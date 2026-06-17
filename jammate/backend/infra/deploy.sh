#!/usr/bin/env bash
# JamMate — deploy backend su Azure in un comando.
# Provisiona l'infrastruttura (Bicep), carica lo schema DB e pubblica le Functions.
#
# Prerequisiti (una volta sola):
#   - Azure CLI         : https://aka.ms/installazurecli
#   - Functions Core v4 : npm i -g azure-functions-core-tools@4
#   - psql (client)     : pacchetto postgresql-client
#   - Node.js 20
#
# Uso:
#   az login
#   export PG_ADMIN_PASSWORD='UnaPasswordForte!'        # obbligatoria
#   export ENTRA_AUDIENCE='...'  ENTRA_ISSUER='...'  ENTRA_JWKS_URI='...'  # opzionali ora
#   ./deploy.sh [prefisso] [regione]
#
# Esempio: ./deploy.sh jammate westeurope
set -euo pipefail

PREFIX="${1:-jammate}"
LOCATION="${2:-westeurope}"
RG="rg-${PREFIX}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(cd "$HERE/.." && pwd)"

echo "▶ JamMate deploy — RG=$RG  regione=$LOCATION"

# --- controlli prerequisiti ---
for bin in az func psql; do
  command -v "$bin" >/dev/null 2>&1 || { echo "✖ Manca '$bin'. Vedi i prerequisiti in cima allo script."; exit 1; }
done
az account show >/dev/null 2>&1 || { echo "✖ Non sei loggato. Esegui: az login"; exit 1; }
: "${PG_ADMIN_PASSWORD:?Imposta PG_ADMIN_PASSWORD (es. export PG_ADMIN_PASSWORD='...')}"

PG_ADMIN_USER="${PG_ADMIN_USER:-jammate_admin}"
ENTRA_AUDIENCE="${ENTRA_AUDIENCE:-}"
ENTRA_ISSUER="${ENTRA_ISSUER:-}"
ENTRA_JWKS_URI="${ENTRA_JWKS_URI:-}"

# --- 1) resource group ---
echo "▶ [1/5] Creo il resource group…"
az group create -n "$RG" -l "$LOCATION" -o none

# --- 2) infrastruttura (Bicep) ---
echo "▶ [2/5] Deploy infrastruttura (Bicep)… (qualche minuto)"
az deployment group create -g "$RG" -f "$HERE/main.bicep" -o none \
  -p namePrefix="$PREFIX" location="$LOCATION" \
     pgAdminUser="$PG_ADMIN_USER" pgAdminPassword="$PG_ADMIN_PASSWORD" \
     entraAudience="$ENTRA_AUDIENCE" entraIssuer="$ENTRA_ISSUER" entraJwksUri="$ENTRA_JWKS_URI"

OUT() { az deployment group show -g "$RG" -n main --query "properties.outputs.$1.value" -o tsv; }
FUNC_NAME="$(OUT functionAppName)"
FUNC_URL="$(OUT functionAppUrl)"
PG_FQDN="$(OUT pgServerFqdn)"
DB_NAME="$(OUT databaseName)"
PG_SERVER="${PG_FQDN%%.*}"

# --- 3) firewall: consenti il tuo IP per caricare lo schema ---
echo "▶ [3/5] Apro temporaneamente il firewall DB per il tuo IP…"
MYIP="$(curl -s https://api.ipify.org || true)"
if [ -n "$MYIP" ]; then
  az postgres flexible-server firewall-rule create -g "$RG" -n "$PG_SERVER" \
    --rule-name deploy-client --start-ip-address "$MYIP" --end-ip-address "$MYIP" -o none
fi

# --- 4) carico lo schema ---
echo "▶ [4/5] Carico schema.sql nel database…"
export PGPASSWORD="$PG_ADMIN_PASSWORD"
psql "host=$PG_FQDN port=5432 dbname=$DB_NAME user=$PG_ADMIN_USER sslmode=require" \
  -v ON_ERROR_STOP=1 -f "$BACKEND/schema.sql"

# --- 5) pubblico le Functions ---
echo "▶ [5/5] Pubblico le Azure Functions…"
( cd "$BACKEND/functions" && npm install --omit=dev --no-audit --no-fund && func azure functionapp publish "$FUNC_NAME" )

echo
echo "✅ Deploy completato."
echo "   API:    $FUNC_URL"
echo "   Health: $FUNC_URL/v1/health   (atteso: {\"status\":\"ok\",\"db\":\"up\"})"
echo
echo "Prossimi passi:"
echo "  • Configura Entra External ID e reimposta ENTRA_* (vedi DEPLOY_AZURE.md, Passo 3)."
echo "  • Nel frontend attiva JM.Api con base URL = $FUNC_URL (vedi api.js)."
echo "  • Per azzerare tutto: az group delete -n $RG --yes"
