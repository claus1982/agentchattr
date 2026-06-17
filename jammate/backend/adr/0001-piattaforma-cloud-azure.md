# ADR 0001 — Piattaforma cloud: Azure

**Stato:** Accettato · **Data:** 2026-06-16

## Contesto
Il prototipo è una PWA con dati finti in `localStorage`. Per diventare
un'app reale serve un backend multi‑utente: account, dati condivisi,
pagamenti, residenza dati UE (GDPR). L'utente dispone di una **licenza
Microsoft aziendale** con possibili crediti cloud.

## Decisione
Costruiamo il backend su **Microsoft Azure**.

## Razionale
- **Costo marginale ~0**: la licenza aziendale può coprire i consumi iniziali
  (poche decine di €/mese), togliendo il principale freno al lancio.
- **GDPR nativo**: data‑center UE (West Europe / Italy North), strumenti di
  compliance e residenza dati integrati.
- **Stack coerente**: identità (Entra), compute, DB, storage, realtime e
  sicurezza (Key Vault, WAF, Defender) sotto un unico fornitore e una sola
  fattura/identità.
- **Competenze/ecosistema** già presenti nel contesto aziendale dell'utente.

## Conseguenze
- (+) Spesa iniziale potenzialmente azzerata; perimetro di sicurezza completo.
- (−) Lieve **lock‑in** verso Azure. Mitigazione: usiamo mattoni portabili
  (**PostgreSQL** standard, **OpenAPI**, codice applicativo in Node) così la
  logica resta migrabile; lo strato Azure è soprattutto infrastruttura.
- Il deploy richiede accesso a una subscription Azure (lato utente).

## Alternative considerate
- **Firebase / Supabase (BaaS)**: time‑to‑market più rapido, ma costo a carico
  nostro, minore controllo su residenza/compliance enterprise e nessun
  vantaggio dalla licenza esistente.
- **AWS / GCP**: validi tecnicamente, ma non sfruttano la licenza Microsoft e
  introducono un fornitore in più nel contesto dell'utente.
