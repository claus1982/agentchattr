# 🎸 JamMate — Prototipo (MVP)

App per musicisti: trova chi suona vicino a te e suonate insieme dal vivo.
Questo è un **prototipo funzionante** (Progressive Web App) per validare l'idea — non la versione finale.

## Cosa c'è dentro (i 3 pilastri che contano)
- **Scopri** 🔍 — cerca musicisti con filtri incrociati: strumento + livello + genere + distanza.
- **Profilo** 🎵 — con la marcia in più di JamMate: il **repertorio con le tonalità esatte**.
- **Bacheca** 📌 — annunci di band/jam con "slot strumenti mancanti" e candidature.
- Più: una **chat** demo e la creazione di annunci.

> Non incluse di proposito in questo MVP (verranno dopo, solo se la gente usa le prime): metronomo, accordatore, sistema di feedback completo. La ricerca di mercato dice di validare prima il cuore dell'app.

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
