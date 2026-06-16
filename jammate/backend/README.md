# JamMate — Backend (Tappa 2)

Questa cartella contiene il **contratto** del backend, prima ancora di scrivere
codice server. Servono per costruire l'app multi‑utente reale su Azure
(vedi `../ARCHITECTURE_AZURE.md`).

## File
- **`openapi.yaml`** — Contratto API: tutti gli endpoint che le Azure Functions
  esporranno (profili, scoperta/match, band, locali, prenotazioni, chat,
  webhook Stripe). È il riferimento condiviso fra frontend e backend.
- **`schema.sql`** — Schema del database PostgreSQL (Azure Database for
  PostgreSQL, regione UE). Eseguibile così com'è per creare le tabelle.
- **`adr/`** — Architecture Decision Records: il **perché** di ogni scelta
  (Azure, Functions, PostgreSQL, Entra, Stripe, ecc.) con alternative scartate.
- **`functions/`** — Scheletro delle Azure Functions (Node.js v4) generato dal
  contratto: auth Entra, accesso DB e primi endpoint, pronto da completare.

## Come si lega al frontend
Il frontend ora passa **sempre** da `../storage.js` (data layer). Oggi quel
modulo scrive nel browser (`localStorage`); domani gli aggiungeremo un backend
`api` che chiama gli endpoint definiti qui in `openapi.yaml`. La UI non cambia.

## Prossimi passi (quando colleghiamo Azure)
1. Creare le risorse Azure (regione UE) e applicare `schema.sql` al database.
2. Generare lo scheletro delle Azure Functions dal contratto `openapi.yaml`.
3. Configurare Microsoft Entra External ID per login/registrazione.
4. Implementare il backend `api` in `storage.js` e attivarlo.

> Nota: il deploy richiede l'accesso alla subscription Azure (lato utente).
> Il codice e la guida passo‑passo li prepara l'assistente.
