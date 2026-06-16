# JamMate API — Azure Functions (scheletro)

Scheletro del backend (Node.js, modello v4) generato dal contratto
[`../openapi.yaml`](../openapi.yaml). Pronto da completare e pubblicare su Azure
quando colleghiamo la subscription (vedi `../../ARCHITECTURE_AZURE.md` e gli ADR).

## Struttura
```
functions/
├─ host.json                 # config runtime (routePrefix: v1)
├─ package.json              # dipendenze (@azure/functions, pg, jwt, jwks)
├─ local.settings.json.example  # variabili (in prod: Key Vault + Managed Identity)
└─ src/
   ├─ lib/
   │  ├─ db.js               # pool PostgreSQL + transazioni
   │  ├─ auth.js             # validazione JWT Entra + utente JIT
   │  └─ http.js             # risposte JSON + withAuth/safe (gestione errori)
   └─ functions/
      ├─ health.js           # GET  /v1/health            ✅ completo
      ├─ me.js               # GET/PUT/DELETE /v1/me       ✅ completo
      ├─ discover.js         # GET  /v1/discover           🟡 query ok, affinità da collegare (Tappa 4)
      ├─ swipes.js           # POST /v1/swipes             ✅ completo (con logica match)
      └─ bookings.js         # GET/POST/PATCH /v1/bookings 🟡 manca autorizzazione + Stripe (Tappa 5/6)
```
Endpoint ancora da aggiungere (definiti in `openapi.yaml`): bands, venues,
reviews, threads/messages, webhooks/stripe, me/deep, me/photo.

## Eseguire in locale
```bash
cd backend/functions
npm install
cp local.settings.json.example local.settings.json   # poi compila i valori
func start                                            # richiede Azure Functions Core Tools v4
# API su http://localhost:7071/v1/...
```
Serve un PostgreSQL con lo schema applicato:
```bash
psql "$PG_CONNECTION_STRING" -f ../schema.sql
```

## Principi di sicurezza già nello scheletro
- **Nessuna password gestita da noi**: solo token Entra firmati (`auth.js`, ADR 0004).
- **Query parametriche** ovunque (anti SQL‑injection) — vedi `db.js`.
- **TLS obbligatorio** verso il DB; segreti fuori dal codice (Key Vault in prod).
- **Errori centralizzati**: nessun dettaglio interno esposto al client (`http.js`).
- TODO marcati nel codice dove vanno aggiunti i controlli di **autorizzazione
  per‑oggetto** (anti‑IDOR) e l'integrazione **Stripe**.

## Deploy su Azure (sintesi — guidato al momento del collegamento)
1. Crea Function App (Node 20, regione UE) + PostgreSQL Flexible + Key Vault.
2. Abilita **Managed Identity** e concedi accesso ai segreti in Key Vault.
3. Imposta le app settings (connessione DB, valori Entra, Stripe) da Key Vault.
4. `func azure functionapp publish <nome-app>`.
5. Applica `schema.sql` al database e configura CORS verso il dominio della PWA.
