# JamMate — Feedback Valerio Gabrielli (16/06/2026)

Triage del feedback del primo tester. Legenda stato:
**✅ Fatto** (già nel prototipo) · **🔜 Prossimo** (a breve, frontend) · **🔭 Roadmap** (più grande / richiede backend o design).

> Contesto: questi miglioramenti girano sul prototipo attuale (dati locali).
> Le voci 🔭 più grandi (mappa, feed, notifiche realtime, lezioni) si
> innestano naturalmente sul backend Azure già progettato (vedi `backend/`).

---

## 🐛 Bug risolti
| # | Segnalazione | Stato | Note |
|---|---|---|---|
| 1 | **La band non si salvava** | ✅ Fatto | Il pulsante passava l'evento del click come "band da modificare": il salvataggio veniva saltato. Corretto (anche per il profilo Locale). |

## ✅ Già implementato dal feedback
| # | Richiesta | Stato | Note |
|---|---|---|---|
| 2 | **Livello per ogni strumento** + più livelli | ✅ Fatto | Scala a 6: Principiante · Principiante‑Intermedio · Intermedio · Intermedio‑Avanzato · Avanzato · Professionista. Nel profilo imposti un livello per ciascuno strumento; le card mostrano "Strumento · Livello". |
| 3 | **Filtri in bacheca** + "darli automaticamente" | ✅ Fatto | Filtri per strumento e genere, "solo slot liberi", e toggle **🎯 Per me** che mostra gli annunci adatti ai tuoi strumenti/generi. |
| 4 | Profilo profondo: "rivedi" mostrava solo "rifai" | ✅ Fatto | Aggiunta vista **📊 Rivedi i risultati** (Big Five, valori top, stile in band) separata da "Rifai". |

## ✅ Quick‑win frontend completati
| # | Richiesta | Stato | Note di realizzazione |
|---|---|---|---|
| 5 | **Livello per‑strumento anche in onboarding** | ✅ Fatto | In registrazione, appena scegli uno strumento appare una riga **strumento → livello** (scala a 6). Niente più livello unico: imposti subito il livello di ciascuno strumento. |
| 6 | **Invitare musicisti nella band** | ✅ Fatto | Dal dettaglio di un musicista in "Scopri" → **🎸 Invita nella tua band**: scegli ruolo/strumento e messaggio. In "Palco › La mia band" vedi la sezione **Formazione & inviti** con stato (in attesa / in formazione / declinato); puoi annullare o rimuovere. Nel prototipo l'accettazione è simulata; col backend (tabella `band_invites`) diventa invito reale + notifica + accettazione. |
| 7 | **Contatore jam a cui hai partecipato** | ✅ Fatto | Campo `jamCount` sul profilo, incrementato quando segni una **serata completata** in Palco. Sul profilo compare un **badge a traguardi** (✨ Pronto → 🎸 Esordiente → 🥉/🥈/🥇 → 🏆 Leggenda). |
| 8 | **Metronomo: migliorie** | ✅ Fatto | Già presenti accenti, battute (2/4…6/4) e tap‑tempo. Aggiunti **suoni selezionabili** (Beep, Click, Legno, Cowbell) con anteprima e **salvataggio preset** (nome + BPM + battute + suono, con carica/elimina). |

## 🔭 Roadmap (più grandi / con backend Azure)
| # | Richiesta | Priorità | Note |
|---|---|---|---|
| 9 | **Mappa con jam geolocalizzate** | Alta ⭐ | Pubblichi "suono il giorno X alle Y" e appare sulla mappa; gli altri vedono le jam vicine, in **verde quelle a cui possono partecipare** in base a strumento/livello. **Accesso ibrido (deciso): chi crea la jam sceglie per ogni evento** se è "aperta agli idonei" (entri subito) o "su approvazione" (richiesta → conferma dell'autore). Richiede: geolocalizzazione, mappa, eventi con data/luogo, regole di idoneità + flag `accessMode`. Si appoggia alle tabelle `open_nights`/eventi del DB. |
| 10 | **Notifiche in tempo reale** | Alta | Inviti band, nuove jam vicine, candidature, messaggi. Si realizza con Azure Web PubSub + notifiche push (vedi ADR 0007). |
| 11 | **Feed sociale** (post e foto di jam/attività) | Media | Bacheca sociale con post, foto, like/commenti. Nuove tabelle (posts, media su Blob Storage) + moderazione. |
| 12 | **Sezione Lezioni** con calendario | Media | Profili insegnante, disponibilità, prenotazione su calendario. **Deciso: prenotazione + pagamento online fin dal primo rilascio** (riusa Stripe, vedi ADR 0006: escrow/commissione come per le serate). |
| 13 | **Accordatore: trasposizione in tempo reale** | Media | **Deciso: implementiamo un default ora**, da affinare con Valerio. Default (vedi sotto). |
| 14 | **Accordatore: verifica precisione note** | Alta | Validare l'algoritmo di pitch detection su note reali (test strumentali) e tarare la soglia di stabilità. |

---

## ✅ Decisioni prese (17/06/2026)
Risposte alle domande aperte, da Claudio (product owner). Queste fissano lo scope per backend e roadmap.

- **Mappa (9) — Accesso ibrido.** Ogni jam pubblica ha un `accessMode` scelto dall'autore:
  - `open`: ogni musicista idoneo (strumento/livello compatibili) **partecipa subito**, senza approvazione;
  - `approval`: l'idoneo **invia una richiesta**, l'autore conferma/rifiuta.
  - Sulla mappa restano **verdi** le jam a cui l'utente è idoneo; per quelle `approval` lo stato passa da "richiesta inviata" a "confermato".
- **Lezioni (12) — Prenotazione + pagamento da subito.** Niente fase "solo prenotazione": al primo rilascio l'insegnante pubblica disponibilità a calendario e l'allievo prenota **e paga online** (Stripe, stesso modello escrow/commissione delle serate).
- **Trasposizione (13) — Default da implementare ora.** Flusso di partenza (da rifinire con Valerio):
  1. L'utente sceglie lo **strumento traspositore** (es. Sax contralto in **Mi♭**, Sax tenore / Clarinetto / Tromba in **Si♭**, strumenti in **Do** = nessuna trasposizione).
  2. L'accordatore rileva la frequenza e mostra **due note affiancate**: **nota reale** (suono concertistico, in Do) e **nota scritta/letta** dallo strumentista (trasposta dell'intervallo del suo strumento).
  3. Indicatore di intonazione (cent ±) riferito alla nota reale.
  - Intervalli default: Mi♭ → nota scritta una **sesta maggiore sopra** il suono reale; Si♭ → una **seconda maggiore sopra**. Configurabile, così Valerio può correggere casi particolari.

> Citazione dal feedback: *"già così praticamente è un gran bel prototipo
> funzionante"* — ottimo punto di partenza. 🎸
