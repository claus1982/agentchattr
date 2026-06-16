# JamMate — Sicurezza: stato attuale, minacce e roadmap di hardening

> Documento onesto. **Premessa importante:** "a prova di hacker al 100%" non esiste — la sicurezza è *difesa a strati* (defense‑in‑depth) e un lavoro continuo. Qui distinguo **cosa è già protetto oggi** (prototipo) da **cosa va costruito quando ci sarà il backend** (account, pagamenti, dati reali).

---

## 1. Architettura attuale = superficie d'attacco ridotta
Oggi JamMate è una **PWA statica** (HTML/CSS/JS) servita da **GitHub Pages**, con i dati salvati **solo nel browser** (`localStorage`). **Non c'è server applicativo, né database, né login/pagamenti reali**: tutto (utenti, match, prenotazioni, recensioni) è simulato sul dispositivo.

Conseguenza diretta:
- **DoS/DDoS sul "nostro server": non applicabile oggi.** Non esiste un nostro server da saturare. I file statici sono serviti dalla **CDN di GitHub/Fastly**, che assorbe il traffico e la mitigazione DDoS a livello infrastrutturale.
- **Furto del database: non applicabile oggi.** Non c'è un DB centrale: non esistono dati di altri utenti da rubare. Ogni dato resta sul singolo telefono.
- **Trasporto cifrato: già attivo.** GitHub Pages serve **solo su HTTPS/TLS** (traffico cifrato in transito).

## 2. Rischi reali del prototipo (lato client) e cosa abbiamo fatto
| Rischio | Stato | Mitigazione applicata |
|---|---|---|
| **XSS** (iniezione di codice via testi utente) | mitigato | Tutto l'input mostrato passa da `esc()` (escape di `& < > " '`). I **link** del profilo ora passano da `safeUrl()` → consentiti **solo** `http/https` (blocca `javascript:`/`data:`). Rimosso l'unico gestore `onclick` inline. |
| **Script esterni / injection** | mitigato | **Content‑Security‑Policy** severa: `script-src 'self'` (niente inline, niente script da domini terzi), `object-src 'none'`, `base-uri 'none'`, `upgrade-insecure-requests`. |
| **Clickjacking / referrer leak** | parziale | `referrer: no-referrer`. `frame-ancestors`/`X-Frame-Options` richiedono header lato server (vedi §4: serve un host che imposti header, es. Cloudflare). |
| **Dipendenze di terzi (supply chain)** | basso | **Nessuna libreria JS di terze parti** (codice tutto nostro). Unica risorsa esterna: i Google Fonts (CSS+font). Opzione di hardening: **self‑host dei font** per azzerare la dipendenza esterna. |
| **Dati locali** | informare | `localStorage` **non è cifrato** ed è leggibile da qualunque JS sulla stessa origine. Oggi contiene solo dati demo non sensibili. **Regola:** mai metterci segreti/token/carte. |
| **Microfono (accordatore)** | ok | Usato solo su gesto utente, su HTTPS; nessuna registrazione salvata o inviata. |

## 3. Cosa NON è (ancora) in gioco e perché
Le richieste tipiche — "criptata, anti‑DoS, anti‑hacker" — riguardano per il **99% il backend** che oggi non esiste. Diventano centrali in **Fase 2** (account reali, pagamenti, dati di più utenti). Senza backend non c'è login da forzare, né API da floodare, né DB da esfiltrare.

---

## 4. Roadmap di sicurezza per la produzione (quando arriva il backend)
Checklist allineata a **OWASP Top 10** e alle buone pratiche.

### Trasporto & header
- **HTTPS/TLS ovunque** + **HSTS** (forza https).
- Header di sicurezza (servono un host con header custom — es. dietro **Cloudflare**): `Content-Security-Policy`, `Strict-Transport-Security`, `X-Frame-Options: DENY`/`frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy` (microfono solo dove serve).

### Autenticazione & sessioni
- Password **hashate** con **bcrypt/argon2** (mai in chiaro), policy di robustezza, **MFA** opzionale.
- Sessioni sicure (cookie `HttpOnly`+`Secure`+`SameSite`, o JWT a vita breve con refresh), logout/revoca.
- **Rate‑limit sul login** + lockout progressivo + CAPTCHA su abuso (anti brute‑force / credential stuffing).
- Login social/OAuth (Google/Apple) per ridurre la gestione password.

### DoS / DDoS / abuso
- **CDN + WAF** davanti a tutto (Cloudflare/Fastly): mitigazione volumetrica, regole anti‑bot.
- **Rate limiting** per IP/utente sulle API, **limiti di dimensione** delle richieste e degli upload, timeouts.
- **Autoscaling** e circuit breaker; code per i picchi.
- CAPTCHA/challenge su endpoint sensibili (registrazione, invio messaggi, recensioni).

### Validazione input / OWASP
- **Query parametrizzate/ORM** → niente **SQL injection**.
- **Output encoding** + CSP → niente **XSS**; token **anti‑CSRF** sulle azioni di stato.
- Controlli di **autorizzazione a livello di oggetto** (anti **IDOR**: l'utente A non può leggere/modificare le prenotazioni di B), ruoli (membro band vs admin vs locale).
- **Upload foto**: validazione **lato server** (tipo MIME reale, dimensione, **ri‑codifica dell'immagine** per rimuovere payload/EXIF, scansione antivirus, storage separato senza esecuzione).

### Cifratura & segreti
- **Cifratura at‑rest** del database (e dei backup); **KMS** per le chiavi.
- Segreti/API key in un **vault** (mai nel codice/repo); rotazione.
- **Dati di personalità (Sintonia) = categoria sensibile** → cifratura, minimizzazione, accesso ristretto.

### Pagamenti
- **Mai gestire/è memorizzare i dati delle carte**: delega a **Stripe** (PCI‑DSS gestito da loro). Stripe Connect per i payout → evita licenze da *money transmitter* e fa il **KYC**.
- Verifica delle dispute/chargeback, anti‑frode, escrow con rilascio a evento concluso.

### Privacy / legale (Italia/UE)
- **GDPR**: consenso esplicito, diritto all'oblio (cancellazione account+dati), portabilità, data minimization, registro trattamenti, DPO se necessario.
- Recensioni conformi a **Omnibus/DSA** (vietato falsificare/sopprimere).

### Anti‑abuso / fiducia
- Recensioni **solo post‑transazione verificata** (già progettato), anti‑fake (rilevazione pattern/rete), prevenzione **Sybil** (verifica email+telefono, probation nuovi account).
- Anti‑disintermediazione (mascheramento contatti pre‑booking).

### Processo & monitoraggio
- **Dipendenze**: minime, scanning automatico (SCA/Dependabot), versioni pinnate, **SRI** per eventuali asset da CDN.
- **Logging & monitoring** (accessi anomali, alert), **backup** regolari testati, piano di **incident response**.
- **Pen‑test** periodici e (a regime) **bug bounty**; code review di sicurezza nelle PR.
- Segregazione ambienti (dev/stage/prod), least privilege sugli accessi cloud.

---

## 5. Cosa è stato cambiato in questa revisione (commit)
- `safeUrl()` + uso sui link del profilo (anti‑XSS via `javascript:`/`data:`).
- Rimosso l'`onclick` inline → possibile **CSP senza `unsafe-inline` per gli script**.
- Aggiunta **CSP** e `referrer: no-referrer` in `index.html`.

## 6. Messaggio onesto
Per il **prototipo** la superficie d'attacco è minima e ora è ragionevolmente irrobustita lato client. La parte "seria" (account, pagamenti, dati di molti utenti) va progettata **insieme al backend in Fase 2**, seguendo la checklist qui sopra. Consiglio, prima del lancio reale con dati veri, una **verifica di sicurezza dedicata** (pen‑test) e una consulenza **GDPR**.
