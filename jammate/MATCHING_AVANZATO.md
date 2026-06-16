# JamMate — Matching avanzato: fondamento scientifico e proposta

> Come rendere il matching "fine" e psicologicamente fondato senza promettere cose che la scienza dice impossibili. Documento di design con fonti. Data: 2026-06-16.

---

## ⭐ Verdetto in tre righe
Sì, esiste molta scienza solida e riutilizzabile (personalità, valori, dinamiche di band). MA la ricerca dimostra anche che **prevedere la "chimica" tra due persone da un test fatto prima di conoscersi funziona quasi come il caso.** Quindi la mossa intelligente **non** è "lo screening che trova l'anima gemella", ma un **punteggio di Affinità trasparente** che (a) filtra i no secchi, (b) ordina i profili e (c) fa da rompighiaccio. Usato così, è un vero vantaggio competitivo. Promesso come "match perfetto garantito", è un boomerang.

---

## 1. Cosa NON fare (la verità scomoda, ma utile)
Due studi chiave:
- **Finkel et al. (2012), *Online Dating: A Critical Analysis***: "non c'è alcuna prova convincente che un algoritmo di matching online funzioni davvero" nel predire la compatibilità di coppia.
- **Joel, Eastwick & Finkel (2017)**: con 100+ misure self-report e machine learning, la parte che conta — quanto due *specifiche* persone si desiderano a vicenda — era **sostanzialmente impredicibile**. Predicibile invece: quanto uno è *in generale* desiderabile e quanto è *in generale* selettivo.

➡️ **Implicazione di design:** la chimica nasce dall'incontro, non dal questionario. Quindi:
- **niente** linguaggio tipo "compatibilità 98% = match perfetto";
- l'algoritmo serve a **ordinare, filtrare e dare spunti**, non a garantire;
- ottimizzare il *farsi incontrare* batte ogni questionario più lungo.

❌ E soprattutto: **MBTI no.** È pseudoscienza (dicotomie forzate, bassa affidabilità test-retest, manca la dimensione emotiva). Usiamo i **Big Five (OCEAN)**, lo standard scientifico.

---

## 2. Cosa SÌ fare: i segnali che la scienza supporta

### A. Valori e obiettivi allineati = il predittore più forte di "durare insieme"
La ricerca sul *person-group fit* (Kristof-Brown et al., 2005) e sulla coesione (la **coesione di compito** conta più di quella sociale) dice che la cosa che fa sopravvivere un gruppo è **condividere obiettivo e livello di impegno**. Per una band la domanda madre è: *"siamo qui per divertirci o per sfondare?"*. Il mismatch qui distrugge band anche bravissime. → **Similarità sugli obiettivi/valori.**

### B. Ruoli e competenze complementari (qui sì "opposti")
Similarità sui valori, **complementarità sui ruoli/strumenti**. Gli studi sui quartetti d'archi (Murnighan & Conlon, 1991) mostrano che funziona chi bilancia leadership e democrazia e gestisce lo status dei ruoli. → strumenti diversi che si incastrano, non cloni.

### C. Affidabilità (Coscienziosità): l'anti-"batterista che sparisce"
La **Coscienziosità** è il tratto Big Five più legato alla resa di un team; un solo membro inaffidabile ("anello debole") affonda il gruppo. → parametro **affidabilità** pesante (collegabile anche agli endorsement post-jam su puntualità).

### D. Il "trio dell'andare d'accordo"
Più si va d'accordo con: **bassa Instabilità emotiva (Neuroticism), alta Gradevolezza (Agreeableness), alta Coscienziosità** (Malouff et al., 2010). Effetti modesti (r ≈ .06–.22): spostano le probabilità, non sono deterministici → peso **basso** nel punteggio.

### E. Gusto musicale condiviso = legame reale (via valori)
Boer et al. (2011): condividere i gusti musicali aumenta l'attrazione interpersonale, **perché i gusti segnalano valori condivisi**. Rentfrow & Gosling: la musica è *il* tema con cui gli sconosciuti si conoscono, e da una top-10 si intuisce la personalità. → il tuo overlap di **generi + repertorio** non è gadget: è un segnale scientificamente valido. (Modello **MUSIC**: Mellow/Unpretentious/Sophisticated/Intense/Contemporary.)

### F. Variabili "da musicista" che pesano davvero (oltre il genere)
Originali vs cover · improvvisazione vs struttura · livello tecnico simile · energia/tempo · frequenza prove e impegno · gestione di ego/conflitti e di crediti/soldi. Sono i fattori che la letteratura (e la pratica delle band) indica come decisivi.

---

## 3. Strumenti validati e GRATIS da riusare (niente ruota da reinventare)
- **Personalità → Mini-IPIP** (20 item, ~2 min): di **dominio pubblico** (IPIP), usabile anche commercialmente. Misura i 5 Big Five. (Alternativa più corta: **BFI-10**, 10 item; più ricca: **BFI-2-S**, 30 item.)
- **Sofisticazione/impegno musicale → Gold-MSI** (Goldsmiths): sottoscale "Musical Training" e "Active Engagement", **validato anche in italiano**. Utile per stimare livello/serietà in modo onesto.
- **Gusto musicale → STOMP / modello MUSIC** (Rentfrow & Gosling): mappa i generi su 5 dimensioni.
- **Bussola valori/obiettivi → questionario custom** (poche domande mirate sui fattori del §2F): è qui che mettiamo la parte "band-specifica" non coperta dai test accademici.

---

## 4. Proposta concreta per JamMate: "Profilo Profondo" + punteggio "Sintonia"

### Due livelli (l'approfondimento è OPZIONALE, come volevi)
1. **Profilo base** (tutti): strumenti, livello, generi, distanza, repertorio. → già fatto.
2. **Profilo Profondo** (opt-in, sondaggio ~3–5 min). Tre blocchi:
   - **🎯 Bussola del musicista** (custom, peso ALTO): obiettivo (hobby↔professione), originali vs cover, improvvisazione vs struttura, frequenza prove desiderata, stile di leadership, approccio al conflitto, affidabilità.
   - **🧠 Personalità** (Mini-IPIP, peso BASSO): i Big Five.
   - **🎼 Identità musicale** (peso MEDIO): dimensioni MUSIC + energia/tempo preferiti.

### Come si calcola la "Sintonia" (trasparente, non magica)
- **Filtri "no secco" (hard)**: distanza, strumento cercato, e mismatch grave di obiettivo/impegno → esclude o avvisa.
- **Punteggio soft (ordina, non promette)** = media pesata di:
  | Componente | Logica | Peso |
  |---|---|---|
  | Obiettivi/valori (Bussola) | **similarità** | alto |
  | Gusto + repertorio in comune | similarità (legame via valori) | medio-alto |
  | Affidabilità/coscienziosità | più alta è meglio | medio |
  | Complementarità di ruolo/strumento | **diversità utile** | medio |
  | Personalità (trio + similarità valori) | similarità, effetti modesti | basso |
- **Spiegazione always-on**: invece di un numero nudo, mostra il *perché* → "Stessi obiettivi (semi-pro), 4 brani in comune, entrambi affidabili, ruoli che si incastrano." Questo è esattamente l'uso scientificamente corretto: **rompighiaccio**, non oracolo.

### Come appare nel profilo
- Badge **"🧬 Profilo Profondo"** sui profili di chi ha fatto il sondaggio.
- Quando **entrambi** l'hanno fatto → compare **"Sintonia XX%"** con la spiegazione. Se uno solo l'ha fatto → "Sintonia disponibile se anche lui/lei completa il Profilo Profondo" (leva virale per farlo compilare).
- Copy onesto, fisso: *"La Sintonia si basa su valori e gusti condivisi: un ottimo punto di partenza, non una garanzia. La vera intesa nasce suonando insieme."*

### Note legali/etiche (Italia/GDPR)
Dati di personalità = categoria sensibile. Sempre **opt-in esplicito**, possibilità di **nascondere** i risultati, e nessuna promessa "scientifica" di compatibilità (Finkel docet). Lo trattiamo come "affinità/cose in comune", non come profilazione psicometrica vincolante.

---

## 5. Perché questo è un vantaggio competitivo
Vampr & co. matchano su strumento/genere/distanza (segnale grossolano). Una **Sintonia** basata su *obiettivi + affidabilità + repertorio in comune*, spiegata in modo trasparente, è (a) più utile, (b) difendibile scientificamente, (c) un motivo per compilare il profilo a fondo (più dati = più stickiness) e (d) un rompighiaccio che aumenta i contatti reali. Il tutto **senza** promettere l'impossibile.

---

### Fonti principali
Personalità/Big Five vs MBTI; Mini-IPIP/BFI-10/BFI-2 (dominio pubblico/free). Similarità vs complementarità: Montoya et al. (2008). Tratti e accordo: Malouff et al. (2010). Team/band: Bell (2007), Kristof-Brown et al. (2005), Murnighan & Conlon (1991), "Band Chemistry" (Rock Music Studies, 2024). Musica & legame: Rentfrow & Gosling (2003/2006), Boer et al. (2011), modello MUSIC (2011), Gold-MSI (Müllensiefen et al., 2014). Limiti del matching: Finkel et al. (2012), Joel/Eastwick/Finkel (2017), Gale-Shapley (allocazione, non predizione). *(URL completi nei report di ricerca.)*
