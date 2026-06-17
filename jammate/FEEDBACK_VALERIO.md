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

## 🔜 Prossimi (frontend, senza backend)
| # | Richiesta | Priorità | Note di realizzazione |
|---|---|---|---|
| 5 | **Livello per‑strumento anche in onboarding** | Media | Oggi l'onboarding usa un livello unico applicato a tutti; poi lo affini nel profilo. Da estendere con selettore per‑strumento in fase di registrazione. |
| 6 | **Invitare musicisti nella band** | Alta | Dai match/seguiti, invita in band. Nel prototipo: lista inviti locale; con backend diventa invito reale + accettazione. |
| 7 | **Contatore jam a cui hai partecipato** | Media | Campo `jamCount` sul profilo + incremento quando una jam/serata è confermata; badge sul profilo. |
| 8 | **Metronomo: migliorie** | Media | Es. accenti/battute (4/4, 3/4…), tap‑tempo, suoni selezionabili, salvataggio preset. |

## 🔭 Roadmap (più grandi / con backend Azure)
| # | Richiesta | Priorità | Note |
|---|---|---|---|
| 9 | **Mappa con jam geolocalizzate** | Alta ⭐ | Pubblichi "suono il giorno X alle Y" e appare sulla mappa; gli altri vedono le jam vicine, in **verde quelle a cui possono partecipare** in base a strumento/livello. Richiede: geolocalizzazione, mappa, eventi con data/luogo, regole di idoneità. Si appoggia alle tabelle `open_nights`/eventi del DB. |
| 10 | **Notifiche in tempo reale** | Alta | Inviti band, nuove jam vicine, candidature, messaggi. Si realizza con Azure Web PubSub + notifiche push (vedi ADR 0007). |
| 11 | **Feed sociale** (post e foto di jam/attività) | Media | Bacheca sociale con post, foto, like/commenti. Nuove tabelle (posts, media su Blob Storage) + moderazione. |
| 12 | **Sezione Lezioni** con calendario | Media | Profili insegnante, disponibilità, prenotazione su calendario, eventualmente pagamento (riusa Stripe). |
| 13 | **Accordatore: trasposizione in tempo reale** | Media | Da approfondire con Valerio ("te la spiego con calma"): trasposizione per strumenti traspositori (es. sax in Mib/Sib) mostrando la nota letta vs scritta. |
| 14 | **Accordatore: verifica precisione note** | Alta | Validare l'algoritmo di pitch detection su note reali (test strumentali) e tarare la soglia di stabilità. |

---

## Domande aperte per Valerio
- **Mappa (9)**: le jam pubbliche sono aperte a tutti gli idonei o servono inviti/approvazione dell'autore?
- **Trasposizione (13)**: quando hai tempo, spiegaci il flusso preciso (strumento di partenza → tonalità desiderata, cosa vuoi vedere a schermo).
- **Lezioni (12)**: solo prenotazione o anche pagamento online fin da subito?

> Citazione dal feedback: *"già così praticamente è un gran bel prototipo
> funzionante"* — ottimo punto di partenza. 🎸
