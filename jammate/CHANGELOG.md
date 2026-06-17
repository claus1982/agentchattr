# JamMate — Changelog

## Non rilasciato — Verso il backend reale su Azure
- **Fix "Solo slot liberi"** (Bacheca): il filtro era una `<label>` con checkbox e
  l'`onclick` invertiva una variabile; l'attivazione della label rilanciava il click
  → doppio toggle, nessun effetto visibile. Ora è un pulsante singolo: funziona.
- **QA rifiniture**: tab bar robusta con 7 voci (i nomi lunghi non sforano più),
  azioni header (🔔) nascoste durante l'onboarding.
- **Feed sociale** (#11): nuova tab 🌐 Feed con post (testo + foto), like e
  commenti; engagement simulato. Nuovo modulo `social.js`.
- **Notifiche** (#10): campanella 🔔 in header con centro notifiche e badge
  non‑letti, alimentata da match, inviti band, jam, prenotazioni, like/commenti.
- **Mappa jam geolocalizzate** (#9): Bacheca › 🗺️ Mappa jam con segnaposti
  (verdi = idonei), creazione jam con accesso ibrido (aperta / su approvazione),
  idoneità per strumento e livello, richieste con approvazione dell'host.
- **Sezione Lezioni** (#12): Palco › 🎓 Lezioni con insegnanti, slot a
  calendario, prenotazione + pagamento (simulato) e modalità "diventa insegnante".
- **Accordatore evoluto** (#13/#14): trasposizione per strumenti traspositori
  (Do/Si♭/Mi♭/Fa, nota reale vs letta), calibrazione La₄ 430–446 Hz, lettura in
  cent con verso e smorzamento del jitter.
- **Onboarding con livello per‑strumento** (feedback #5): in registrazione ogni
  strumento scelto ottiene la sua riga *strumento → livello* (niente più livello
  unico).
- **Contatore jam + badge** (feedback #7): nuovo `jamCount` sul profilo,
  incrementato a ogni *serata completata* in Palco, con badge a traguardi
  (✨ → 🎸 → 🥉/🥈/🥇 → 🏆).
- **Metronomo: suoni e preset** (feedback #8): timbri selezionabili (Beep, Click,
  Legno, Cowbell) con anteprima e salvataggio/caricamento **preset** (nome, BPM,
  battute, suono).
- **Invita musicisti nella band** (feedback Valerio #6): dal dettaglio di un
  musicista in "Scopri" → *🎸 Invita nella tua band* (scegli ruolo e messaggio).
  In "Palco › La mia band" nuova sezione **Formazione & inviti** con stato
  (in attesa / in formazione / declinato), annulla/rimuovi. Accettazione simulata
  nel prototipo; modellato lato backend con la tabella `band_invites`.
- **Decisioni di prodotto fissate** (vedi `FEEDBACK_VALERIO.md`): mappa jam ad
  **accesso ibrido** (l'autore sceglie aperta/su-approvazione), **Lezioni con
  pagamento online da subito** (Stripe), **trasposizione accordatore** con flusso
  di default. Riflesse in `schema.sql` (tabelle `jams`, `jam_participants`,
  `teacher_profiles`, `lesson_slots`, `lesson_bookings`) e ADR 0006.
- **Data layer sostituibile** (`storage.js`): l'app non usa più `localStorage`
  direttamente, ma passa da `JM.Storage`. Pronto a puntare ad Azure senza
  riscrivere la UI. Nessun cambiamento visibile per l'utente.
- **Contratto backend** (`backend/`): `openapi.yaml` (API) + `schema.sql`
  (database PostgreSQL) + architettura Azure (`ARCHITECTURE_AZURE.md`) +
  **ADR** delle scelte (`backend/adr/`) + scheletro **Azure Functions**
  (`backend/functions/`) + guida di **deploy** (`backend/DEPLOY_AZURE.md`).
- **Client API** (`api.js`, `JM.Api`): collega la PWA agli endpoint del backend
  (fetch + token Entra), pronto da attivare al deploy. Non ancora in uso.

## v0.1.0 — Prototipo MVP (2026-06-16)
Prima versione dimostrativa (PWA, dati locali, pagamenti simulati).

### Trova & forma la band
- **Scopri** in modalità *swipe* (stile match) + modalità *ricerca con filtri* (strumento, livello, genere, distanza).
- **Profilo musicale** con repertorio e **tonalità esatte**, foto profilo, link.
- **Bacheca annunci** (cerco/offro musicisti, jam) con slot strumenti e candidature.
- **Chat** interna, sbloccata dal match.

### Sintonia (matching scientifico)
- **Profilo Profondo** opzionale: valori (Schwartz), personalità (Big Five/Mini-IPIP), stile relazionale (circumplex), bussola del musicista.
- Punteggio **Sintonia** trasparente (media geometrica pesata + veto dealbreaker), con spiegazione e **insight** falsificabile (anti-Barnum).
- **Endorsement post-jam** → affidabilità reale, non auto-dichiarata.

### Palco (band ↔ locali)
- Entità **Band** (EPK, formazione, repertorio, badge "Pronta & Disponibile").
- Profilo **Locale/Azienda** che cerca e prenota band.
- Prenotazione con **conferma**, **pagamenti simulati** (escrow + fee 5%), serate multiple.
- **Recensioni a due lati verificate** (solo post-serata, doppio cieco).

### Cassetta degli attrezzi
- **Metronomo** (BPM, tap tempo, accenti) e **Accordatore** (microfono + toni di riferimento).

### Design & sicurezza
- UI premium: font Plus Jakarta Sans, gradienti mesh, dock flottante, avatar premium.
- Hardening lato client: **CSP**, link sanificati (anti-XSS), nessuna dipendenza di terzi. Vedi `SECURITY.md`.

### Documenti
`JAMMATE_RICERCA_MERCATO.md`, `MATCHING_AVANZATO.md`, `MATCHING_V2.md`, `FEATURES_TO_BE.md`, `DESIGN.md`, `SECURITY.md`.

> Nota: prototipo per validazione. Dati finti salvati nel browser; nessun backend/pagamento reale ancora.
