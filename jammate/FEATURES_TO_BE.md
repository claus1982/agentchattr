# JamMate — Feature roadmap "TO BE": Band, Locali & Booking

> Visione: oltre al matchmaking tra musicisti, JamMate diventa il ponte tra **band pronte** e **chi le ingaggia** (locali, aziende, eventi), con prenotazioni, pagamenti protetti e reputazione a due lati. Documento strategico basato su ricerca con fonti (4 indagini: marketplace band‑in‑hire, commissioni/pagamenti, recensioni controllate, entità "band" & disponibilità).

---

## ⭐ Verdetto in breve
L'idea è **solida e c'è uno spazio reale**, soprattutto in Italia:
- I marketplace italiani (Musiqua, iLiveMusic, Showgroup) sono **solo "vetrine/lead‑gen": 0% commissione, nessun pagamento protetto, accordi fuori piattaforma.** Manca un attore **transazionale con prenotazione + pagamento garantito**.
- Le **serate ricorrenti / "residency"** (la tua idea di "combinare più serate") sono **quasi scoperte** anche dai big internazionali (GigSalad, Encore): ottimo differenziatore.
- Nessuno unifica **"band completa + disponibile per serate locali"** in un colpo solo (profilo pronto + disponibilità stasera/questo weekend).

⚠️ Ma attenzione alla sequenza: **i pagamenti/escrow non si costruiscono per primi.** Prima serve liquidità (band e locali presenti). Si parte gratis/lead‑gen, si aggiunge il pagamento protetto quando c'è massa. E gestire denaro ha implicazioni legali serie (vedi §7).

---

## 1. Nuove entità da introdurre
Oggi JamMate ha un'entità: il **musicista**. Servono altre due:

### 🎸 Band (entità, non solo somma di persone)
- Composta da **account membri** con ruoli (admin/leader, membro) — modello "roster" (come Muzeek).
- Profilo band = **EPK** (Electronic Press Kit, lo standard del settore): bio breve+lunga, foto/logo, 2–3 brani e video, repertorio/scaletta, **formazione**, storia concerti, **rider tecnico + stage plot**, pacchetti/prezzi, link social.
- **Badge "Pronta & Disponibile"** = profilo completo (stile "PromoKit 100%" di GigSalad) **+** disponibilità aperta per serate locali. *Questo è l'elemento che nessuno unifica.*

### 🏢 Locale / Azienda (chi ingaggia, "talent buyer")
- Profilo del locale: tipo (pub, club, ristorante, evento privato, azienda), capienza, generi graditi, foto, posizione.
- Strumenti per **cercare band** con filtri (genere, formazione, distanza, budget, data) e **pubblicare richieste** ("cerco cover band anni '80 per sabato, budget X").

---

## 2. Disponibilità & Calendario
Pattern validato dal mercato (GigSalad, Muzeek, BandHelper):
- **Calendario interno privato** della band + **vista pubblica "filtrata"** (mostra solo libero/occupato, non i dettagli) — approccio Muzeek.
- **Disponibilità generale** (es. "disponibili venerdì/sabato sera") + **blocco di date specifiche**.
- **Inbox di richieste data**: il locale chiede una data, la band accetta/rifiuta; le conferme popolano il calendario.
- Sync **iCal/Google** (in sola lettura per iniziare — lo standard è one‑way).

## 3. Flusso di prenotazione (con conferma)
Lo schema standard dei marketplace transazionali:
1. **Ricerca/Richiesta** → il locale trova la band o pubblica una richiesta che instradiamo alle band compatibili e disponibili.
2. **Offerta/Preventivo** → la band invia un preventivo (compenso, durata, cosa è incluso). Chat interna per negoziare.
3. **Conferma** → il locale conferma.
4. **Accordo** → contratto/accordo digitale generato dalla piattaforma (con i termini: data, luogo, compenso, cancellazione).
5. **Pagamento** → acconto alla conferma + saldo, tramite **escrow** (trattenuto e versato dopo la serata).
6. **Recensione** → valutazione reciproca (vedi §5).

➕ **Multi‑serata / Residency** (il tuo "combinare più serate"): una singola richiesta per più date ricorrenti (es. "ogni venerdì di marzo"), con prezzo a pacchetto. **Qui battiamo i concorrenti**, che restano legati al singolo evento.

## 4. Pagamenti & la "piccola percentuale" (monetizzazione)
Dalla ricerca, regole d'oro per una fee "utile ma non scoraggiante":
- **Fee bassa per partire** — sotto il ~5% è percepita come "quasi invisibile" (GigSalad prende 2,5–5% lato artista; ~10–12% lato cliente). Si può **far pagare il cliente, non la band** (o splittare) per non scoraggiare i musicisti. Si cresce poi con **add‑on opzionali** (visibilità, "verificato", pacchetti), non alzando la fee base.
- **Escrow + acconto + cancellazioni a fasce** (es. rimborso pieno fino a 30 gg, parziale fino a 7 gg, niente sotto le 48h) → protegge entrambi e riduce i no‑show.
- **La fee deve "comprare protezione"**: pagamento garantito, risoluzione dispute, profili verificati. Così pagarla sembra un'assicurazione, non una tassa.
- **Anti‑disintermediazione** (il rischio n°1: accordarsi fuori per evitare la fee): **mascherare i contatti prima della prenotazione**, tenere chat e pagamento in‑app, offrire garanzie che esistono solo sulla piattaforma. La fuga è massima subito dopo il match.
- **Tecnologia: Stripe Connect** → instrada i soldi ai conti collegati e opera sotto le *sue* licenze, così **evitiamo di diventare "money transmitter"** (licenze costose) e Stripe gestisce il KYC. (Vedi §7.)

## 5. Reputazione a due lati, controllata (la tua domanda chiave)
Il tuo istinto è giusto: **valutazione reciproca tra chi offre lavoro e chi lo fornisce** alza la qualità da entrambe le parti (è il modello Uber: alza l'aspettativa e "pulisce" i comportamenti scorretti). Come farla *seria*:

- ✅ **Solo dopo una prenotazione COMPLETATA sulla piattaforma** si può recensire. È la leva anti‑fake più forte: per lasciare una recensione falsa servirebbe una transazione vera e pagata. (Modello Amazon "acquisto verificato"/Airbnb/Uber.)
- ✅ **Doppio cieco con finestra di 14 giorni** (modello Airbnb): nessuno vede la recensione dell'altro finché non hanno scritto entrambi (o scade la finestra). Riduce le ritorsioni e fa emergere i giudizi onesti.
- ✅ **Reciproca band ↔ locale**: la band vede se un locale paga in ritardo o tratta male; il locale vede se una band fa buca o delude.
- ✅ **Punteggio "intelligente"**: media **bayesiana** (non la media grezza, gonfiabile con pochi voti) + **peso sulla recency** (i voti recenti contano di più) + **down‑weight dei valutatori sempre troppo severi/generosi** + **diritto di replica** pubblica.

### 👥 E i voti del pubblico (ospiti non‑band)?
**Onestamente: NON farli pesare sulla reputazione ufficiale.** Gli spettatori non sono parte della transazione → impossibile verificarli → porta dritti a **review‑bombing** e account falsi (Sybil). Soluzioni:
- Se proprio si vuole, **solo con presenza verificata** (biglietto/check‑in all'evento), e mostrato come metrica **separata e non vincolante ("fan buzz")**, distinta dal punteggio di booking.
- Meglio ancora: usare **segnali comportamentali** (difficilissimi da falsare) → **ri‑ingaggi** (lo stesso locale che richiama la band), repeat di pubblico, sell‑through dei biglietti. Il "fan che torna" è la validazione più vera e impossibile da brigare.

## 6. La "Cassetta degli attrezzi" estesa (sinergie)
- La **Sintonia** già costruita può estendersi alla **coesione di band** (i membri di una band hanno valori/obiettivi allineati?) → "salute della band".
- Repertorio + tonalità della band = scaletta pronta da mostrare ai locali.

## 7. Legale & sicurezza (da non sottovalutare)
- **Pagamenti**: usare un facilitatore (Stripe Connect) per **non gestire denaro in proprio** ed evitare licenze da money transmitter; loro fanno KYC. Restano a noi l'antifrode e la **tassazione da "marketplace facilitator"** (IVA/imposte): serve consulenza fiscale italiana.
- **Recensioni**: rispettare il **Regolamento UE Omnibus + DSA** (vietato pubblicare recensioni false, obbligo di dichiarare *come* verifichiamo che vengano da clienti reali; sanzioni fino al 4% del fatturato o €2M). Mai permettere ai locali di **sopprimere** le recensioni negative né "gating" sulle positive.
- **Dati**: profili di personalità (Sintonia) = dati sensibili → opt‑in, cancellabili (GDPR).
- **Verifica identità** per band/locali che maneggiano pagamenti.

---

## 🗺️ Roadmap a fasi (sequenza consigliata)

**FASE 0 — già fatta:** matchmaking musicisti + Sintonia + cassetta attrezzi.

**FASE 1 (prototipabile subito, senza soldi/backend):**
- Entità **Band** (crea band dai musicisti, EPK base, badge "Pronta & Disponibile").
- Entità **Locale** + ricerca band con filtri (genere, distanza, budget).
- **Bacheca richieste** lato locale ("cerco band per…") e candidatura band.
- **Richiesta data → preventivo → conferma** (senza pagamento reale: solo accordo).
- **Recensione a due lati** verificata (post‑evento) con doppio cieco.

**FASE 2 (quando c'è massa, serve backend + Stripe):**
- **Pagamenti protetti** (acconto+saldo, escrow via Stripe Connect), cancellazioni a fasce, **fee piccola** (cliente).
- **Multi‑serata/residency** con pacchetti.
- Anti‑disintermediazione (mascheramento contatti, chat in‑app).
- Calendario con sync iCal.

**FASE 3 (scala):**
- Verifica identità/badge, livelli premium (visibilità), strumenti pro per locali, metrica "fan buzz" con check‑in verificato, espansione multi‑città.

---

## 🎯 Posizionamento (perché vinciamo)
1. **Italia transazionale**: dove gli altri sono solo vetrine, noi offriamo **prenotazione + pagamento garantito**.
2. **Serate ricorrenti/residency**: differenziatore quasi unico.
3. **Reputazione a due lati verificata**: qualità più alta, fiducia reale.
4. **Sinergia con la Sintonia**: dal trovare i compagni → formare la band → farla ingaggiare. Nessuno copre tutto il ciclo.
5. **Fee bassa e "che si vede"**: utile, non punitiva.

---

### Fonti principali
Marketplace: GigSalad, The Bash, Encore, Poptop, Function Central, Gigmit, Sonicbids; Italia: Musiqua, iLiveMusic, Showgroup; residency: PlugVerse. Commissioni/pagamenti: Sharetribe, Tidemark, Stripe Connect/Disputes, Avalara. Recensioni: Airbnb (Fradkin et al., doppio cieco), Uber rating, PNAS (fake‑review network detection), FTC Rule 2024 (16 CFR 465), UE Omnibus/DSA, media bayesiana (Evan Miller). Entità band/EPK/disponibilità: Bandzoogle, GigSalad PromoKit, Muzeek roster, BandHelper, Prism.fm, Gigwell. *(URL completi nei report di ricerca.)*
