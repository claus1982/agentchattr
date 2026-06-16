# ADR 0009 — Approccio contract‑first (OpenAPI)

**Stato:** Accettato · **Data:** 2026-06-16

## Contesto
Frontend (PWA) e backend (Azure Functions) verranno sviluppati in tempi diversi.
Senza un contratto condiviso si rischiano disallineamenti, rilavorazioni e bug
di integrazione.

## Decisione
Definiamo **prima** il contratto API in **`backend/openapi.yaml`** (OpenAPI 3),
poi implementiamo backend e frontend **contro** quel contratto. È la **Tappa 2**.

## Razionale
- **Una sola fonte di verità** per endpoint, payload e codici di errore.
- **Lavoro in parallelo**: il data layer `api` può essere scritto contro lo
  schema mentre le Functions vengono implementate (anche con mock).
- **Strumenti**: generazione di client/tipi, mock server, validazione e
  documentazione automatica dall'OpenAPI.
- I nomi/campi rispecchiano già le strutture del prototipo → migrazione lineare.

## Conseguenze
- (+) Integrazione prevedibile, meno sorprese, onboarding più facile.
- (−) Il contratto va **mantenuto aggiornato** insieme al codice: una modifica
  agli endpoint si riflette prima in `openapi.yaml`. Disciplina necessaria.

## Alternative considerate
- **Code‑first** (l'API emerge dal codice): più veloce all'inizio, ma il
  contratto resta implicito e il frontend insegue il backend.
- **GraphQL**: flessibile lato client, ma complessità e curva di
  apprendimento ingiustificate per questo set di endpoint ben definito.
