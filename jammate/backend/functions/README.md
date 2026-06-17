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
      ├─ swipes.js           # POST /v1/swipes (logica match)              ✅
      ├─ messages.js         # GET /matches, GET/POST /messages/{userId}   ✅
      ├─ profile.js          # /repertoire, /deep, /endorsements           ✅
      ├─ bands.js            # /bands, /bands/{id}, inviti (/invites)      ✅
      ├─ venues.js           # /venues, /venues/{id}/nights                ✅
      ├─ bookings.js         # GET/POST/PATCH /v1/bookings                 🟡 autorizzazione + Stripe (Tappa 5/6)
      ├─ jams.js             # /jams, join/requests/participants           ✅
      ├─ posts.js            # /posts, reazioni, commenti                  ✅
      ├─ lessons.js          # /teachers, /teacher, /lesson-bookings       🟡 pagamento Stripe (Tappa 6)
      └─ notifications.js    # GET/PATCH/DELETE /v1/notifications          ✅
```
Tutte le query SQL sono state **validate su PostgreSQL 16 reale** con dati di
esempio. Restano da collegare: **affinità server‑side** (Tappa 4), **autorizzazione
per‑oggetto** dove segnato, **Stripe** (Tappa 6), la generazione **server‑side delle
notifiche** dagli eventi e la **realtime** via Web PubSub (ADR 0007).

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
