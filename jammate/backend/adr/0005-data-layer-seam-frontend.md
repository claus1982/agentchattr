# ADR 0005 — Frontend: data layer sostituibile (`storage.js`)

**Stato:** Accettato · **Data:** 2026-06-16

## Contesto
Il prototipo legge/scrive lo stato direttamente con `localStorage`. Per passare
a un backend reale senza riscrivere la UI (rischio alto e regressioni), serve
disaccoppiare la UI dalla sorgente dati. È la **Tappa 1** della roadmap.

## Decisione
Introduciamo un **data layer** unico (`storage.js`, oggetto `JM.Storage`). L'app
non chiama più `localStorage`: passa sempre dal data layer, che oggi usa un
backend locale (browser) e domani potrà usare un backend `api` (Azure
Functions) senza toccare la UI.

## Razionale
- **Migrazione a basso rischio**: cambiare backend ≠ riscrivere l'app.
- **Funziona da subito**: nessun cambiamento visibile per l'utente; il
  prototipo resta operativo.
- **Testabilità**: backend in memoria come fallback e per i test.
- È il punto in cui aggancieremo l'autenticazione e le chiamate definite in
  `openapi.yaml`.

## Conseguenze
- (+) Confine netto fra presentazione e persistenza; cambio backend isolato.
- (−) Oggi l'interfaccia è sincrona (load/save di un blob). Il backend `api`
  sarà **asincrono e granulare**: quando lo introdurremo, alcuni punti di
  `app.js` andranno resi `async`. È un lavoro previsto e circoscritto al data
  layer, non sparso nella UI.

## Alternative considerate
- **Riscrivere subito tutto verso le API**: troppo rischio in un colpo solo;
  romperebbe il prototipo funzionante.
- **Framework con state management dedicato** (React/Vue + store): cambio di
  stack ingiustificato per un MVP in JS puro senza build step.
