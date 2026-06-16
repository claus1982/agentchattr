# ADR 0002 — Compute: Azure Functions (serverless)

**Stato:** Accettato · **Data:** 2026-06-16

## Contesto
Serve un livello che esegua la logica applicativa (profili, match,
prenotazioni, webhook pagamenti) ed esponga l'API definita in `openapi.yaml`.
All'inizio il traffico sarà basso e imprevedibile.

## Decisione
Usiamo **Azure Functions** (modello serverless, runtime Node.js v4), una
Function per gruppo di endpoint.

## Razionale
- **Paghi a consumo**: a traffico basso il costo tende a zero; nessun server
  sempre acceso da pagare.
- **Scala da sola** con i picchi (es. apertura iscrizioni), senza gestione
  manuale di capacità.
- **Stesso linguaggio del frontend** (JavaScript/Node): un solo skill set,
  riuso diretto del motore `affinity.js` lato server.
- Integrazione nativa con Entra (auth), Key Vault (segreti via Managed
  Identity) e Application Insights (monitoraggio).

## Conseguenze
- (+) Costo iniziale minimo, scalabilità automatica, meno ops.
- (−) **Cold start** possibile sul piano Consumption. Mitigazione: endpoint
  leggeri; se serve, si passa al piano **Premium/Flex** (warm instances) senza
  cambiare codice.
- (−) Limiti di durata per richiesta: ok per API; lavori lunghi andranno su
  code/processi dedicati (non previsti ora).

## Alternative considerate
- **App Service (web app sempre attiva)**: nessun cold start, ma costo fisso
  mensile anche a zero traffico.
- **Container (AKS/Container Apps)**: massima flessibilità, ma complessità ops
  ingiustificata per questa fase.
