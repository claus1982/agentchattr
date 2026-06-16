# ADR 0006 — Pagamenti: Stripe (Connect + escrow)

**Stato:** Accettato · **Data:** 2026-06-16

## Contesto
Il "Palco" è un marketplace band ↔ locale: serve incassare dal locale, trattenere
un **acconto in escrow**, applicare la **commissione JamMate (5%)** e pagare
(payout) la band. Gestire dati di carta in proprio impone l'oneroso ambito
**PCI‑DSS**.

## Decisione
Usiamo **Stripe** con **Stripe Connect** (payout ai destinatari) e PaymentIntent
per acconto/saldo. I dati di carta non transitano né sono salvati da noi: nel DB
teniamo solo **riferimenti** (`stripe_pi_id`, `stripe_transfer_id`). I webhook
Stripe sono ricevuti da una Function con **firma verificata**.

## Razionale
- **PCI delegato a Stripe**: togliamo dalle nostre spalle il rischio e la
  certificazione più pesante.
- **Connect** copre nativamente il modello a tre parti (piattaforma, locale,
  band) con commissione e payout.
- **Escrow/hold**: trattenuta dell'acconto e rilascio dopo la serata.
- Ottima documentazione, SDK, e supporto SCA/3DS (UE).

## Conseguenze
- (+) Conformità e sicurezza pagamenti senza costruirle; nessun costo fisso.
- (−) Commissioni per transazione (~1,5% + fee) — costo solo sul transato reale.
- (−) Stripe non è Azure: un fornitore esterno in più, integrato via webhook
  firmati e segreti in Key Vault.
- Funzionalità prevista in **Tappa 6**: fino ad allora i pagamenti restano
  simulati nel prototipo.

## Alternative considerate
- **PayPal / Mollie / Adyen**: validi; Stripe scelto per DX, Connect maturo e
  diffusione. Rivedibile in base a costi/mercato.
- **Incasso fatto in casa**: scartato — PCI e rischio frodi insostenibili.
