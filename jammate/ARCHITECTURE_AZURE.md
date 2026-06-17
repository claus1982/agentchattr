# JamMate — Architettura backend su Azure (Opzione A)

> Piano per trasformare il prototipo (PWA con dati locali) in un'app **multi‑utente reale** su Azure, sfruttando la licenza aziendale e i data‑center **UE** (GDPR). Documento per non‑tecnici + riferimento tecnico.

---

## 1. Schema dell'architettura
```
[ PWA (browser/telefono) ]  ← la nostra app attuale, invariata come UX
        │  HTTPS
        ▼
[ Azure Static Web Apps ]  → hosting del frontend (CDN globale, dominio tuo)
        │  chiamate API
        ▼
[ Azure Functions (API) ]  → la logica: profili, match, prenotazioni, recensioni
   │           │            │              │
   ▼           ▼            ▼              ▼
[PostgreSQL] [Blob Storage] [Web PubSub]  [Stripe]
 dati app     foto/media     chat realtime  pagamenti
        ▲
[ Microsoft Entra External ID ] → login/registrazione utenti (e social)
```
Tutto in **regione UE** (West Europe o Italy North).

## 2. Componenti (cosa fa ciascuno e perché)
| Pezzo | Servizio Azure | Ruolo |
|---|---|---|
| Frontend | **Azure Static Web Apps** | serve la PWA, dominio personalizzato, HTTPS, integra auth e API |
| Login | **Microsoft Entra External ID** (ex Azure AD B2C) | registrazione/login utenti, social login, MFA, reset password |
| API/logica | **Azure Functions** (serverless) | endpoint sicuri; paghi a consumo (ottimo a basso volume) |
| Database | **Azure Database for PostgreSQL** (Flexible Server) | dati relazionali: utenti, band, prenotazioni, recensioni |
| File/foto | **Azure Blob Storage** | foto profilo/band, media EPK (con ridimensionamento lato server) |
| Chat live | **Azure Web PubSub** (o SignalR) | messaggi in tempo reale |
| Pagamenti | **Stripe** (non Azure) | carte, escrow, payout band; PCI gestito da Stripe |
| Segreti | **Azure Key Vault** | chiavi/API key fuori dal codice |
| Sicurezza perimetro | **Azure Front Door + WAF** / DDoS Protection | CDN, firewall applicativo, mitigazione DDoS |

## 3. Modello dati (tabelle principali)
- **users** (id, email, ruolo, data creazione) ← gestito con Entra
- **musician_profiles** (user_id, nome, città, strumenti, livello, generi, bio, links, foto)
- **repertoire** (profile_id, brano, artista, tonalità)
- **deep_profiles** (user_id, valori[], big5{}, ipc{}, bussola{}) ← per la Sintonia
- **bands** (id, nome, città, fee, generi, badge_disponibile) + **band_members** (band_id, user_id, ruolo)
- **venues** (id, owner_id, nome, tipo, città, capienza, generi)
- **bookings** (id, band_id, venue_id, data, stato, importo, fee, acconto, stripe_ref)
- **reviews** (booking_id, autore, valutazione, testo, rivelata) ← doppio cieco
- **endorsements** (target_user_id, autore_id, puntualità, tecnica, attitudine)
- **messages** (thread_id, mittente, testo, timestamp)

## 4. Sicurezza (dalla checklist di SECURITY.md → strumenti Azure)
- **Trasporto**: HTTPS/TLS ovunque + HSTS (Static Web Apps/Front Door).
- **DDoS/DoS**: Front Door + **WAF** + rate limiting; Azure **DDoS Protection**.
- **Auth**: Entra External ID (password gestite da Microsoft, MFA, brute‑force protection integrata).
- **Autorizzazione**: controlli per‑oggetto nelle Functions (anti‑IDOR), ruoli (membro/admin band, locale).
- **Cifratura**: PostgreSQL e Blob **cifrati at‑rest** di default; segreti in **Key Vault**; **Managed Identity** (niente password nei servizi).
- **Upload foto**: validazione + ri‑codifica lato Function, storage isolato.
- **Monitoraggio**: **Application Insights** + **Microsoft Defender for Cloud** (alert, posture).
- **Pagamenti**: Stripe (PCI), webhook firmati verificati in Function.
- **GDPR**: regione UE, consenso, cancellazione account/dati, dati personalità cifrati e minimizzati.

## 5. Costi (stima realistica, basso volume iniziale)
- Static Web Apps: **gratis/quasi** (tier free generoso).
- Functions: **a consumo**, pochi €/mese a basso traffico.
- PostgreSQL Flexible (Burstable B1ms): **~15–35 €/mese**.
- Blob Storage: **pochi € /mese**.
- Web PubSub: tier free per iniziare.
- Entra External ID: **gratis** fino a decine di migliaia di utenti attivi/mese.
- Stripe: **nessun fisso**, ~1,5% + commissioni sulle transazioni reali.
➡️ **In partenza, ordine di grandezza poche decine di €/mese**, plausibilmente **coperto dai crediti enterprise**. Cresce col volume.

## 6. Roadmap a tappe (piccoli passi, ognuno verificabile)
1. **Fondamenta**: refactor del frontend con un **"data layer" sostituibile** (oggi localStorage → domani API), senza cambiare la UX. *(Costruibile SUBITO, resta tutto funzionante.)*
2. **Contratto API + schema DB**: definizione endpoint (OpenAPI) e schema PostgreSQL. *(Costruibile subito nel repo.)*
3. **Auth + profili reali**: Entra External ID + tabelle utenti/profili → primi account veri.
4. **Sintonia server‑side**: il motore `affinity.js` diventa una Function (riuso del codice già scritto).
5. **Palco/prenotazioni** su DB con stati e autorizzazioni.
6. **Pagamenti** Stripe (escrow, acconto, payout, webhook).
7. **Chat realtime** con Web PubSub.
8. **Hardening + GDPR + pen‑test** prima del lancio pubblico.

## 7. Cosa serve da te (quando partiamo col cloud)
- Accesso a una **subscription Azure** (o un *resource group* dedicato) con permessi per creare risorse.
- Un account **Stripe** (per i pagamenti, fase 6).
- Un **dominio** (es. jammate.it) se vuoi un indirizzo tuo.
- Decisioni: regione (West Europe vs Italy North), nome prodotto/dominio.

## 8. Cosa posso costruire SUBITO senza toccare Azure
- **Tappa 1 e 2**: il "data layer" sostituibile nel frontend + il **contratto API (OpenAPI)** + lo **schema SQL** del database, già committati nel repo e pronti al deploy.
- Lo scheletro delle **Azure Functions** (codice) da pubblicare poi nella tua subscription con la mia guida passo‑passo.

> Nota onesta: il deploy vero su Azure lo fai tu (servono le tue credenziali/subscription) — io scrivo tutto il codice e ti guido clic‑per‑clic. Da qui non posso accedere al tuo Azure.
