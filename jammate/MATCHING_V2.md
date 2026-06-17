# JamMate — Algoritmo "Sintonia" v2 (specifica)

Motore: `affinity.js` (modulo isolato, estraibile come servizio Axiovra). Questa è la versione 2, calibrata su ricerca approfondita (vedi anche `MATCHING_AVANZATO.md`).

## Strumenti di misura (tutti gratuiti / dominio pubblico o autoriali)
| Blocco | Strumento | Item | Nota |
|---|---|---|---|
| Valori | Modello di **Schwartz** (10 valori, item in stile "ritratto") | 10 | centratura within-person (MRAT) |
| Personalità | **Mini-IPIP** (Big Five) — dominio pubblico | 20 | usato per "positività", non per matching |
| Stile relazionale | **IPIP-IPC** ridotto (Dominanza/Calore) — dominio pubblico | 8 | per la complementarità di ruolo |
| Bussola musicista | custom (obiettivi, cover/originali, prove, energia, affidabilità) | 7 | parte band-specifica |

Il **Profilo Profondo è opzionale**; il motore usa solo i blocchi presenti in entrambi gli utenti e **ripesa** (degradazione elegante). Indicatore di "profondità": Base → Buono → Approfondito → Completo.

## Componenti, direzione e peso (a fasce su effect-size)
| Componente | Direzione (evidenza) | Peso |
|---|---|---|
| **Valori condivisi** | similarità — correlazione di profilo centrata (Boer 2011; Leikas 2018) | 3 (alto) |
| **Obiettivi & impegno** | similarità (person-group fit, Kristof-Brown 2005) | 3 (alto) |
| **Gusti & repertorio** | overlap generi + brani | 2.5 |
| **Affidabilità** | "anello debole" = il minore dei due (Bell 2007) | 2 |
| **Modo di suonare** | similarità (cover/originali, improvvisazione, energia) | 1.5 |
| **Ruoli (IPC)** | complementarità sulla **dominanza** + similarità sul **calore** (Sadler/Woody) | 1.5 |
| **Carattere (Big Five)** | "positività" (bassa N, alta A/C) + lieve similarità (Malouff 2010) | 1 (basso) |

## Aggregazione
- **Media geometrica pesata** dei sotto-punteggi (non compensatoria, come l'HDI ONU dal 2010): un crollo in una dimensione non viene mascherato da un'altra.
- **Veto sui dealbreaker**: obiettivi molto distanti (hobby vs pro) abbassano il punteggio (×0.72) e generano un avviso; mismatch di affidabilità → avviso.
- Output mappato in **40–98%** (niente 0 scoraggianti né 100% "garantito").

## Principi metodologici rispettati
- **Niente "difference score" grezzi** (critica di Edwards): ogni costrutto ha la *direzione giusta* (similarità vs complementarità).
- **Centratura** dei valori (MRAT) per togliere lo stile di risposta; profilo confrontato via correlazione.
- **Pesi a fasce**, non finta precisione a 2 decimali (i pesi unitari sono difficili da battere — Bobko 2007).
- **Onestà**: la chimica reale è quasi impredicibile prima di conoscersi (Joel/Finkel 2017) → la Sintonia è **ranking soft + rompighiaccio**, mai una garanzia.

## Insight "sorprendente" (serendipity, anti-Barnum)
Una frase **specifica e falsificabile** che cita il dato, in ordine di priorità:
1. **Valore profondo condiviso** (inferito dal test, non ovvio)
2. **Complementarità di ruolo** (differenza inquadrata come risorsa)
3. **Brano in comune** (rilevanza concreta e immediata)
4. Stessa **ambizione** / **genere** condiviso

Accompagnato da un **"Ti risuona?"** (👍/🤔) per costruire fiducia *calibrata*, non cieca.

## Roadmap di calibrazione (quando ci saranno dati reali)
- Validare le direzioni/forme con **polynomial regression + Response Surface Analysis** su esiti reali (match andati a buon fine, band durate).
- De-trend rispetto al profilo *normativo* (per non gonfiare le affinità su valori comuni a tutti).
- A/B test del peso dei blocchi; passare da pesi a-priori a pesi appresi solo se battono i pesi a fasce.
