# ADR 0004 — Identità: Microsoft Entra External ID

**Stato:** Accettato · **Data:** 2026-06-16

## Contesto
Serve registrazione/login per utenti finali (musicisti, locali), con social
login, reset password, MFA opzionale. L'autenticazione è un'area ad alto
rischio: gestire password e sessioni in proprio è pericoloso e oneroso
(vedi `SECURITY.md`).

## Decisione
Deleghiamo l'identità a **Microsoft Entra External ID** (la soluzione CIAM di
Azure, evoluzione di Azure AD B2C). Le Functions accettano token **JWT Bearer**
emessi da Entra e li validano.

## Razionale
- **Non gestiamo password**: niente hashing, niente reset, niente brute‑force
  da arginare a mano — lo fa Microsoft. Rischio enorme tolto dalle nostre mani.
- **Funzioni pronte**: social login, MFA, verifica email, protezione anti‑abuso.
- **Integrazione nativa** con Static Web Apps e Functions; coerente con ADR 0001.
- **Costo**: gratis fino a decine di migliaia di utenti attivi/mese.
- **GDPR**: gestione consensi e dati di login in regione UE.

## Conseguenze
- (+) Sicurezza dell'autenticazione di livello enterprise senza scriverla noi.
- (−) Dipendenza dal tenant Entra (coerente con la scelta Azure).
- Nel DB teniamo solo il profilo applicativo legato al `sub` del token, non le
  credenziali (vedi tabella `users` in `schema.sql`).

## Alternative considerate
- **Auth fatta in casa** (email+password nostre): massimo controllo, ma
  superficie di rischio e manutenzione altissime. Scartata.
- **Auth0 / Clerk**: ottimi prodotti, ma fornitore e costo aggiuntivi; nessun
  vantaggio rispetto a Entra dato il contesto Azure.
