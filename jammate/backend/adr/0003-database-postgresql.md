# ADR 0003 — Database: PostgreSQL (relazionale)

**Stato:** Accettato · **Data:** 2026-06-16

## Contesto
I dati di JamMate sono fortemente **relazionali e transazionali**: utenti,
band e membri, locali, prenotazioni con stati, recensioni a doppio cieco,
pagamenti. Servono integrità referenziale e query incrociate (filtri per
città/strumento/genere, affinità).

## Decisione
Usiamo **Azure Database for PostgreSQL — Flexible Server** (regione UE).
Schema in `backend/schema.sql`.

## Razionale
- **Relazioni e vincoli** (foreign key, CHECK sugli stati, UNIQUE su coppie
  swipe/endorsement) proteggono la coerenza dei dati: è il cuore del dominio.
- **Transazioni ACID**: confermare una prenotazione e muovere un acconto in
  escrow deve essere atomico.
- **Query ricche**: indici GIN su `genres`/`instruments` (array), JSONB per i
  dati di personalità, join per discover/affinità.
- **Standard e portabile**: niente lock‑in di query language; migrabile altrove.
- Cifratura at‑rest di default, backup gestiti.

## Conseguenze
- (+) Modello dati solido, integro, interrogabile.
- (−) Costo fisso minimo del server (tier Burstable B1ms, ~15–35 €/mese) anche
  a basso traffico; accettabile e scalabile in verticale quando serve.
- Va gestita la connessione dalle Functions (pool / connessione efficiente).

## Alternative considerate
- **Cosmos DB (NoSQL)**: ottimo per scala globale e schemi liberi, ma le nostre
  relazioni e transazioni multi‑entità diventerebbero scomode e costose.
- **MySQL**: equivalente, ma PostgreSQL offre JSONB/array/indici GIN più adatti
  ai nostri campi (generi, strumenti, profilo profondo).
