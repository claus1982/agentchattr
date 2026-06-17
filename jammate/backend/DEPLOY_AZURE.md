# JamMate — Guida al deploy su Azure (passo‑passo)

> Guida pratica per portare JamMate online su Azure, da seguire **insieme**
> quando sei al PC con accesso alla subscription. Pensata per non‑tecnici:
> ogni passo dice *dove cliccare* e *cosa scrivere*. Tutto in **regione UE**.
>
> Riferimenti: architettura in `../ARCHITECTURE_AZURE.md`, scelte in `adr/`,
> contratto API in `openapi.yaml`, schema DB in `schema.sql`, codice in `functions/`.

## 🚀 Deploy automatico (1 comando) — consigliato
Per chi ha già **Azure CLI + Functions Core Tools + psql** sul PC, c'è uno script
che fa tutto (infrastruttura, schema DB, pubblicazione Functions) via
Infrastructure‑as‑Code (`infra/main.bicep`):

```bash
az login
export PG_ADMIN_PASSWORD='UnaPasswordMoltoForte!'
# opzionali ora (si possono impostare dopo aver creato l'app Entra, Passo 3):
# export ENTRA_AUDIENCE='...'  ENTRA_ISSUER='...'  ENTRA_JWKS_URI='...'
cd jammate/backend/infra
./deploy.sh jammate westeurope
```

Lo script crea il resource group `rg-jammate`, provisiona **PostgreSQL Flexible**,
**Function App** (Node 20) con Storage e Application Insights, **Key Vault** (con la
connection string letta via Managed Identity), apre temporaneamente il firewall DB
per il tuo IP, **carica `schema.sql`** e **pubblica le Functions**. Alla fine stampa
l'URL dell'API e l'endpoint `/v1/health`.

> Lo schema è già stato **validato su PostgreSQL 16 reale** (23 tabelle, vincoli e
> default OK). Il resto richiede la *tua* subscription: esegui lo script dal tuo PC
> (o da una pipeline) con `az login` fatto.
>
> Preferisci procedere a clic dal **portale**? Segui la guida manuale qui sotto. ⤵️

---

## Prima di iniziare (10 minuti)
- [ ] Accesso a una **subscription Azure** (o un *resource group* dedicato) con permessi di creare risorse — chiedi all'IT aziendale se la licenza è enterprise.
- [ ] Browser su **https://portal.azure.com** (login con l'account aziendale).
- [ ] Sul tuo PC, installa (una volta sola):
  - **Azure CLI** → https://aka.ms/installazurecli
  - **Azure Functions Core Tools v4** → `npm i -g azure-functions-core-tools@4`
  - **Node.js 20** → https://nodejs.org
- [ ] Decidi due cose: **regione** (consiglio *West Europe*) e un **prefisso nome** (es. `jammate`). I nomi globali (storage, function app) devono essere unici: useremo `jammate<qualcosa>`.

> 💡 Useremo il **portale** (clic) per creare le risorse e la **CLI/Functions
> Tools** solo per caricare il codice e lo schema. Niente di irreversibile finché
> non inserisci dati reali.

---

## Passo 1 — Gruppo di risorse (il "contenitore")
1. Portale → barra di ricerca in alto → **Resource groups** → **+ Create**.
2. *Subscription*: la tua. *Resource group*: `rg-jammate`. *Region*: **West Europe**.
3. **Review + create** → **Create**.

✅ Ora tutte le risorse staranno insieme in `rg-jammate` (facile da monitorare e, se serve, cancellare in blocco).

---

## Passo 2 — Database PostgreSQL
1. Ricerca → **Azure Database for PostgreSQL flexible servers** → **+ Create** → *Flexible server*.
2. *Resource group*: `rg-jammate`. *Server name*: `jammate-db` (sarà `jammate-db.postgres.database.azure.com`). *Region*: West Europe.
3. *Workload type*: **Development** (tier economico). *Compute + storage* → scegli **Burstable B1ms** (il più piccolo) → **Save**.
4. *Authentication*: **PostgreSQL authentication only**. Imposta utente `jammate_admin` e una **password forte** (annotala).
5. **Next: Networking** → *Connectivity*: **Public access** → spunta **Allow public access from any Azure service…** e aggiungi il tuo IP (pulsante *Add current client IP*).
6. **Review + create** → **Create** (qualche minuto).
7. Quando è pronto: apri il server → **Databases** → **+ Add** → nome `jammate`.

✅ Hai un database vuoto. Lo schema lo carichiamo al Passo 6.

---

## Passo 3 — Identità utenti (Microsoft Entra External ID)
> Questo dà a JamMate login/registrazione senza gestire password (ADR 0004).
1. Ricerca → **Microsoft Entra External ID** → crea un **tenant esterno (CIAM)** se non ne hai uno (segui il wizard; *External* / *Customer*). *Region* dati: **Europe**.
2. Nel tenant esterno → **App registrations** → **+ New registration**:
   - *Name*: `JamMate`.
   - *Supported account types*: account in questo tenant (clienti).
   - *Redirect URI*: tipo **Single-page application (SPA)**, valore provvisorio `http://localhost:3000` (lo aggiorneremo col dominio reale).
   - **Register**.
3. Annota **Application (client) ID** e **Directory (tenant) ID** dalla pagina *Overview*.
4. **Authentication** → assicurati che ci sia la piattaforma *SPA* e abilita *Access tokens* e *ID tokens*.
5. Crea un **user flow** di registrazione/accesso: nel tenant → **External Identities** → **User flows** → **+ New** → *Sign up and sign in* → seleziona Email/password (+ social opzionali) → associa l'app `JamMate`.

📝 Da qui ricaviamo i 3 valori per le Functions:
- `ENTRA_AUDIENCE` = Application (client) ID
- `ENTRA_ISSUER` = `https://<tenant>.ciamlogin.com/<tenant-id>/v2.0`
- `ENTRA_JWKS_URI` = `https://<tenant>.ciamlogin.com/<tenant-id>/discovery/v2.0/keys`

> ⚠️ I nomi esatti delle voci in Entra External ID cambiano spesso: ti guido a
> schermo. Se qualcosa non combacia, fermiamoci e lo risolviamo insieme.

---

## Passo 4 — Cassaforte dei segreti (Key Vault)
1. Ricerca → **Key vaults** → **+ Create**. *Resource group*: `rg-jammate`. *Name*: `kv-jammate-<tuo-suffisso>`. *Region*: West Europe. **Create**.
2. Apri il vault → **Secrets** → **+ Generate/Import**, crea questi segreti:
   - `PG-CONNECTION-STRING` = `postgres://jammate_admin:<password>@jammate-db.postgres.database.azure.com:5432/jammate?sslmode=require`
   - (più avanti, Tappa 6) `STRIPE-SECRET-KEY`, `STRIPE-WEBHOOK-SECRET`.

✅ I segreti non staranno mai nel codice. Le Functions li leggeranno via *Managed Identity* (Passo 5).

---

## Passo 5 — Function App (il backend)
1. Ricerca → **Function App** → **+ Create** → *Consumption*.
2. *Resource group*: `rg-jammate`. *Name*: `jammate-api-<tuo-suffisso>` (unico globale). *Runtime stack*: **Node.js**, versione **20 LTS**. *Region*: West Europe. *Operating System*: **Linux**.
3. *Storage*: lascia che ne crei uno nuovo. **Review + create** → **Create**.
4. Apri la Function App → **Identity** → *System assigned* → **On** → **Save** (così ottiene un'identità per accedere al Key Vault).
5. Torna al **Key Vault** → **Access control (IAM)** → **+ Add role assignment** → ruolo **Key Vault Secrets User** → assegna alla *Managed Identity* della Function App.
6. Function App → **Configuration** → **Application settings** → aggiungi (i segreti via riferimento al vault):
   - `PG_CONNECTION_STRING` = `@Microsoft.KeyVault(SecretUri=https://kv-jammate-<...>.vault.azure.net/secrets/PG-CONNECTION-STRING/)`
   - `ENTRA_AUDIENCE`, `ENTRA_ISSUER`, `ENTRA_JWKS_URI` = i valori del Passo 3
   - **Save**.

---

## Passo 6 — Carica schema DB e codice
Sul tuo PC, nel terminale:
```bash
# 1) login
az login

# 2) applica lo schema al database (usa la connection string del Passo 4)
psql "postgres://jammate_admin:<password>@jammate-db.postgres.database.azure.com:5432/jammate?sslmode=require" -f jammate/backend/schema.sql

# 3) pubblica le Functions
cd jammate/backend/functions
npm install
func azure functionapp publish jammate-api-<tuo-suffisso>
```
Verifica che il backend risponda:
```bash
curl https://jammate-api-<tuo-suffisso>.azurewebsites.net/v1/health
# atteso: {"status":"ok","db":"up", ...}
```

✅ Se `db:"up"`, backend e database parlano. 🎉

---

## Passo 7 — Frontend online (Static Web Apps)
1. Ricerca → **Static Web Apps** → **+ Create**. *Resource group*: `rg-jammate`. *Name*: `jammate-web`. *Plan*: **Free**. *Region*: West Europe.
2. *Deployment*: collega il repo GitHub `claus1982/agentchattr`, branch a scelta, *App location* = `jammate`. (In alternativa deploy manuale con la CLI `swa`.)
3. A deploy finito avrai un URL tipo `https://jammate-web.azurestaticapps.net`.

---

## Passo 8 — Collega frontend e backend
1. **CORS**: Function App → **CORS** → aggiungi l'URL della Static Web App (e `http://localhost:3000` per i test) → **Save**.
2. **Redirect Entra**: torna alla registrazione app (Passo 3) → **Authentication** → aggiorna l'URI SPA con l'URL reale del frontend.
3. **Attiva il backend nel data layer**: nel frontend imposteremo `JM.Storage.use(apiBackend)` con l'indirizzo del backend (lo implementiamo insieme — è il pezzo che collega la PWA alle Functions).

---

## Passo 9 — Verifica end‑to‑end
- [ ] Apri il sito → **Registrati** (crei un account vero via Entra).
- [ ] Completa il **profilo** → ricarica la pagina: i dati restano (sono nel DB, non più nel browser).
- [ ] Da un secondo account, fai **like** reciproco → deve comparire il **match**.
- [ ] `GET /v1/health` resta `ok`.

---

## Costi e pulizia
- A basso traffico: **poche decine di €/mese** (il grosso è il PostgreSQL Burstable). Functions, Static Web Apps ed Entra restano quasi a zero.
- Per **mettere in pausa la spesa**: fermare/eliminare il PostgreSQL è la voce principale.
- Per **azzerare tutto**: elimina il resource group `rg-jammate` (cancella in blocco ogni risorsa). ⚠️ Operazione irreversibile.

---

## Cosa resta dopo (roadmap)
- **Affinità server‑side** (Tappa 4): portare `affinity.js` in `discover.js`.
- **Pagamenti** (Tappa 6): Stripe Connect + webhook (segreti già predisposti).
- **Chat realtime** (Tappa 7): Azure Web PubSub.
- **Hardening + WAF/DDoS + DPIA GDPR** (Tappa 8) prima del lancio pubblico.

> 🔒 Promemoria: non committare mai `local.settings.json` né password/segreti.
> In produzione vivono solo nel Key Vault.
