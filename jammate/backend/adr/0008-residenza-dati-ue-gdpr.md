# ADR 0008 — Residenza dati: regione UE (GDPR)

**Stato:** Accettato · **Data:** 2026-06-16

## Contesto
JamMate tratta dati personali di residenti UE, inclusi dati delicati: il
**profilo profondo** (valori, personalità Big Five, stile interpersonale) usato
dal motore Sintonia può rientrare tra i dati che richiedono tutela rafforzata.
Il GDPR impone base giuridica, minimizzazione, diritti dell'interessato e
attenzione ai trasferimenti extra‑UE.

## Decisione
Tutte le risorse Azure (DB, storage, Functions, identità) in **regione UE**
(West Europe o Italy North). Misure GDPR integrate nel design:
- **Minimizzazione**: salviamo solo ciò che serve al match.
- **Consenso esplicito** per il profilo profondo; uso limitato all'affinità.
- **Cifratura**: at‑rest di default; per i dati di personalità valutiamo
  cifratura a livello colonna (vedi `deep_profiles` in `schema.sql`).
- **Diritti**: cancellazione account/dati (`DELETE /me`, `deleted_at`),
  esportazione dati su richiesta.

## Razionale
- Obbligo normativo e fiducia degli utenti.
- La scelta Azure (ADR 0001) rende la residenza UE semplice e nativa.
- Ridurre il trasferimento di dati personali fuori UE riduce rischio legale.

## Conseguenze
- (+) Conformità e trasparenza fin dal design ("privacy by design").
- (−) Vincoli sulla scelta di regione/servizi e su eventuali fornitori terzi
  (es. Stripe) di cui va verificato il trattamento dati UE.
- Prima del lancio pubblico: informativa privacy, registro trattamenti e, se
  necessario, DPIA per i dati di personalità.

## Alternative considerate
- **Regione USA / multi‑regione globale**: latenza migliore in alcune aree ma
  complessità GDPR e rischio trasferimenti. Scartata per un prodotto UE‑first.
