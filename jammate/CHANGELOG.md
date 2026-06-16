# JamMate — Changelog

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
