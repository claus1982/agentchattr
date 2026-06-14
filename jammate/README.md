# 🎸 JamMate — Prototipo (MVP)

App per musicisti: trova chi suona vicino a te e suonate insieme dal vivo.
Questo è un **prototipo funzionante** (Progressive Web App) per validare l'idea — non la versione finale.

## Cosa c'è dentro
- **Scopri** 🔥 — due modalità:
  - **Match**: scorri i profili stile "swipe" (come Vampr) con **punteggio di compatibilità** basato su generi, distanza e **brani in comune**. Quando c'è interesse reciproco → **è un match!** e si sblocca la chat.
  - **Cerca**: filtri incrociati (strumento + livello + genere + distanza), risultati ordinati per compatibilità.
- **Profilo** 🎵 — con la marcia in più di JamMate: il **repertorio con le tonalità esatte**.
- **Bacheca** 📌 — annunci di band/jam con "slot strumenti mancanti" e candidature; puoi crearne di tuoi.
- **Chat** 💬 — messaggistica interna senza scambiarsi il numero.
- **Cassetta degli attrezzi** 🧰 — **Metronomo** (BPM, tap tempo, accenti) e **Accordatore** col microfono (rilevamento nota + cent) con toni di riferimento per chitarra.

> Manca solo il sistema di feedback/endorsement completo post-jam (i punteggi sono mostrati ma non ancora assegnabili): è il prossimo pezzo naturale dopo la validazione.

## Come provarla (3 modi, dal più semplice)

### 1) Sul computer
Apri il file `index.html` con un doppio clic (si apre nel browser). Funziona quasi tutto. *(Per avere anche l'installazione come app serve il modo 2 o 3.)*

### 2) Live sul telefono — gratis, con GitHub Pages
1. Su GitHub vai su questo repository → **Settings → Pages**.
2. Source: *Deploy from a branch*, scegli il branch e la cartella `/jammate` (oppure root).
3. Dopo qualche minuto avrai un link tipo `https://tuonome.github.io/...`.
4. Aprilo dal telefono → menu del browser → **"Aggiungi a schermata Home"**: ora JamMate è un'icona sul telefono e si apre a schermo intero come un'app vera.

### 3) In locale come server
```bash
cd jammate
python3 -m http.server 8080
# poi apri http://localhost:8080 nel browser
```

## Dati
Il prototipo è precaricato con musicisti ed eventi finti a **Milano** così vedi subito un'app "piena". I tuoi dati restano nel browser (niente server). Nel profilo c'è il pulsante **"Azzera dati demo"** per ripartire da zero.

## Stack (per chi svilupperà)
HTML + CSS + JavaScript puro, **nessun framework e nessun build step**. PWA installabile (`manifest.webmanifest` + `sw.js`). Facile da far evolvere e, in futuro, da impacchettare in app nativa (es. con Capacitor) riusando lo stesso codice.
