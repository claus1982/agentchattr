/* JamMate — Affinity Engine v2 ("Sintonia")
 * ===========================================================================
 * Modulo ISOLATO e riusabile (estraibile come servizio Axiovra).
 * Fondamento scientifico (vedi MATCHING_AVANZATO.md / MATCHING_V2.md):
 *  - Valori di Schwartz: congruenza = correlazione di profilo CENTRATA (MRAT)
 *    -> segnale di similarità più forte (Boer 2011; Leikas 2018)
 *  - Personalità Big Five (Mini-IPIP, dominio pubblico): peso BASSO, conta più
 *    la "positività" (bassa N, alta A/C) che il matching (Malouff 2010; PMC6034067)
 *  - Circumplex interpersonale (IPIP-IPC): complementarità sulla DOMINANZA,
 *    similarità sul CALORE (Sadler/Woody) -> evidenza moderata, segnale soft
 *  - Bussola del musicista: obiettivi/impegno (person-group fit, Kristof-Brown)
 *  - Aggregazione: MEDIA GEOMETRICA pesata (non compensatoria, come l'HDI) +
 *    veto sui dealbreaker (Edwards: niente difference-score grezzi)
 *  - Pesi a FASCE su effect-size (i pesi unitari sono difficili da battere:
 *    Bobko 2007) -> niente falsa precisione
 *  - Insight: serendipity spiegabile e falsificabile, anti-effetto-Barnum
 *  - CAVEAT (Joel/Finkel): la chimica è quasi impredicibile -> punteggio SOFT
 * =========================================================================== */

// ---- Mini-IPIP (20 item, dominio pubblico) — Big Five ----
const IPIP_ITEMS = [
  { t: "E", rev: false, q: "Sono l'anima della festa." },
  { t: "A", rev: false, q: "Provo empatia per i sentimenti degli altri." },
  { t: "C", rev: false, q: "Sbrigo subito i compiti da fare." },
  { t: "N", rev: false, q: "Ho frequenti sbalzi d'umore." },
  { t: "O", rev: false, q: "Ho una fantasia vivace." },
  { t: "E", rev: true,  q: "Non parlo molto." },
  { t: "A", rev: true,  q: "Non mi interessano i problemi degli altri." },
  { t: "C", rev: true,  q: "Spesso dimentico di rimettere le cose al loro posto." },
  { t: "N", rev: true,  q: "Sono rilassato/a per la maggior parte del tempo." },
  { t: "O", rev: true,  q: "Non mi interessano le idee astratte." },
  { t: "E", rev: false, q: "Alle feste parlo con tante persone diverse." },
  { t: "A", rev: false, q: "Percepisco le emozioni degli altri." },
  { t: "C", rev: false, q: "Amo l'ordine." },
  { t: "N", rev: false, q: "Mi turbo facilmente." },
  { t: "O", rev: true,  q: "Faccio fatica a capire concetti astratti." },
  { t: "E", rev: true,  q: "Tendo a restare in disparte." },
  { t: "A", rev: true,  q: "Non mi interessano davvero gli altri." },
  { t: "C", rev: true,  q: "Combino pasticci." },
  { t: "N", rev: true,  q: "Raramente mi sento giù." },
  { t: "O", rev: true,  q: "Non ho molta immaginazione." }
];

// ---- Valori (modello di Schwartz, 10 valori — item in stile "ritratto") ----
const VALUE_KEYS = ["Autodirezione", "Stimolazione", "Edonismo", "Successo", "Potere",
                    "Sicurezza", "Conformità", "Tradizione", "Benevolenza", "Universalismo"];
const VALUE_ITEMS = [
  { v: "Autodirezione", q: "Per me conta avere idee originali e fare le cose a modo mio." },
  { v: "Stimolazione",  q: "Cerco spesso novità, avventura ed esperienze eccitanti." },
  { v: "Edonismo",      q: "Godermi la vita e divertirmi è una mia priorità." },
  { v: "Successo",      q: "Voglio avere successo e che riconoscano i miei risultati." },
  { v: "Potere",        q: "Mi piace avere influenza e guidare gli altri." },
  { v: "Sicurezza",     q: "Ho bisogno di stabilità, ordine e ambienti sicuri." },
  { v: "Conformità",    q: "Cerco di rispettare le regole e non disturbare gli altri." },
  { v: "Tradizione",    q: "Rispetto le tradizioni e i modi di fare consolidati." },
  { v: "Benevolenza",   q: "Mi prendo cura delle persone vicine e le aiuto volentieri." },
  { v: "Universalismo", q: "Mi stanno a cuore la giustizia, l'uguaglianza e l'ambiente." }
];

// ---- Stile interpersonale (IPIP-IPC ridotto): Dominanza & Calore ----
const IPC_ITEMS = [
  { ax: "D", rev: false, q: "Tendo a prendere il comando nei gruppi." },
  { ax: "D", rev: false, q: "Mi viene naturale dire agli altri cosa fare." },
  { ax: "D", rev: true,  q: "Preferisco che siano gli altri a decidere." },
  { ax: "D", rev: true,  q: "Faccio fatica a impormi." },
  { ax: "W", rev: false, q: "Sono caloroso/a e affettuoso/a con gli altri." },
  { ax: "W", rev: false, q: "Mi fido facilmente delle persone." },
  { ax: "W", rev: true,  q: "Tendo a tenermi a distanza dagli altri." },
  { ax: "W", rev: true,  q: "Faccio fatica a interessarmi ai problemi altrui." }
];

// ---- Bussola del musicista (custom, band-specifica) ----
const BUSSOLA = [
  { id: "goal",    q: "Cosa cerchi dalla musica?",            lo: "Puro divertimento", hi: "Diventare professionista" },
  { id: "orig",    q: "Originali o cover?",                   lo: "Solo cover",         hi: "Solo brani originali" },
  { id: "improv",  q: "Come ti piace suonare?",               lo: "Tutto preparato",    hi: "Tanta improvvisazione" },
  { id: "rehear",  q: "Quanto vuoi provare?",                 lo: "Saltuariamente",     hi: "Più volte a settimana" },
  { id: "energy",  q: "Che energia preferisci?",              lo: "Calma / acustica",   hi: "Intensa / potente" },
  { id: "reliab",  q: "Quanto sei affidabile e puntuale?",    lo: "Vado a sensazione",  hi: "Estremamente affidabile" },
  { id: "reliabW", q: "Quanto conta l'affidabilità altrui?",  lo: "Poco",               hi: "Tantissimo" }
];

// Pesi a fasce su effect-size (3=alto, 2=medio, 1=basso). Normalizzati a runtime.
const TIERS = {
  values: 3,        // congruenza di valori: predittore più forte
  goal: 3,          // obiettivi/impegno
  taste: 2.5,       // gusti + repertorio
  reliability: 2,   // affidabilità (anello debole)
  style: 1.5,       // modo di suonare
  role: 1.5,        // complementarità di ruolo (IPC)
  personality: 1    // Big Five (positività)
};

// ============================ CORE GENERICO ================================
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const sim5 = (a, b) => 1 - Math.abs(a - b) / 4;
const norm5 = (x) => (x - 1) / 4;
const mean = (arr) => arr.reduce((s, v) => s + v, 0) / (arr.length || 1);

function pearson(a, b) {
  const n = a.length; if (!n) return 0;
  const ma = mean(a), mb = mean(b);
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { const x = a[i] - ma, y = b[i] - mb; num += x * y; da += x * x; db += y * y; }
  if (da === 0 || db === 0) return 0;
  return num / Math.sqrt(da * db);
}

// --- Scoring dei blocchi (dalle risposte 1..5) ---
function scoreBig5(answers) {
  const acc = { O: [], C: [], E: [], A: [], N: [] };
  IPIP_ITEMS.forEach((it, i) => acc[it.t].push(it.rev ? 6 - (answers[i] || 3) : (answers[i] || 3)));
  const out = {}; for (const t in acc) out[t] = norm5(mean(acc[t])); return out; // 0..1
}
function scoreValues(answers) {
  const raw = VALUE_ITEMS.map((_, i) => answers[i] || 3);
  const m = mean(raw);                       // MRAT (centratura within-person)
  const out = {}; VALUE_ITEMS.forEach((it, i) => out[it.v] = raw[i] - m); return out;
}
function scoreIPC(answers) {
  const d = [], w = [];
  IPC_ITEMS.forEach((it, i) => { const v = it.rev ? 6 - (answers[i] || 3) : (answers[i] || 3); (it.ax === "D" ? d : w).push(v); });
  return { D: (mean(d) - 3) / 2, W: (mean(w) - 3) / 2 }; // ~ -1..1
}

// --- Overlap gusti/repertorio ---
function tasteOverlap(a, b) {
  const ga = a.genres || [], gb = b.genres || [];
  const gShared = ga.filter(g => gb.includes(g));
  const gScore = ga.length && gb.length ? gShared.length / Math.min(ga.length, gb.length) : 0;
  const ra = (a.repertoire || []).map(r => r.title.toLowerCase());
  const rb = (b.repertoire || []).map(r => r.title.toLowerCase());
  const songs = (a.repertoire || []).filter(r => rb.includes(r.title.toLowerCase()));
  return { score: clamp01(0.55 * gScore + 0.45 * clamp01(songs.length / 3)), genres: gShared, songs: songs.map(s => s.title) };
}

/* computeAffinity(A, B): profili completi (.genres .repertoire .instruments .deep)
 * Usa SOLO i blocchi presenti in entrambi (degradazione elegante), ripesando.
 * Ritorna { score, parts[], warn[], insight{}, depth } */
function computeAffinity(A, B) {
  const a = A.deep || {}, b = B.deep || {};
  const comps = [];  // {key, s, label, text}
  const warn = [];

  // Valori (similarità: correlazione di profilo già centrata)
  if (a.values && b.values) {
    const va = VALUE_KEYS.map(k => a.values[k] ?? 0), vb = VALUE_KEYS.map(k => b.values[k] ?? 0);
    const r = pearson(va, vb);
    comps.push({ key: "values", s: clamp01((r + 1) / 2), label: "Valori condivisi", text: valuesText(a.values, b.values, r) });
  }
  // Obiettivi/impegno (similarità) + veto
  if (a.goal != null && b.goal != null) {
    const s = (sim5(a.goal, b.goal) + sim5(a.rehear ?? 3, b.rehear ?? 3)) / 2;
    comps.push({ key: "goal", s, label: "Obiettivi & impegno", text: goalText(a.goal, b.goal) });
    if (Math.abs(a.goal - b.goal) >= 3) warn.push("Obiettivi molto diversi (hobby vs professione)");
  }
  // Gusti + repertorio
  const taste = tasteOverlap(A, B);
  comps.push({ key: "taste", s: taste.score, label: "Gusti & repertorio", text: tasteText(taste) });
  // Affidabilità (anello debole)
  if (a.reliab != null && b.reliab != null) {
    comps.push({ key: "reliability", s: norm5(Math.min(a.reliab, b.reliab)), label: "Affidabilità", text: "Conta per entrambi la serietà negli impegni" });
    if ((a.reliabW >= 4 && b.reliab <= 2) || (b.reliabW >= 4 && a.reliab <= 2)) warn.push("Possibile attrito sull'affidabilità");
  }
  // Stile (modo di suonare)
  if (a.orig != null && b.orig != null) {
    const s = (sim5(a.orig, b.orig) + sim5(a.improv ?? 3, b.improv ?? 3) + sim5(a.energy ?? 3, b.energy ?? 3)) / 3;
    comps.push({ key: "style", s, label: "Modo di suonare", text: "Approccio compatibile (cover/originali, prove, energia)" });
  }
  // Ruoli (complementarità dominanza, similarità calore)
  if (a.ipc && b.ipc) {
    const domComp = clamp01(0.5 - (a.ipc.D * b.ipc.D) / 2); // opposti = bene
    const warmSim = 1 - Math.abs(a.ipc.W - b.ipc.W) / 2;    // simili = bene
    comps.push({ key: "role", s: clamp01(0.5 * domComp + 0.5 * warmSim), label: "Ruoli (leader/supporto)", text: roleText(a.ipc, b.ipc) });
  }
  // Personalità (positività + leggera similarità)
  if (a.big5 && b.big5) {
    const pos = (mean([a.big5.A, b.big5.A]) + mean([a.big5.C, b.big5.C]) + (1 - mean([a.big5.N, b.big5.N]))) / 3;
    const sim = 1 - (["O", "C", "E", "A", "N"].reduce((s, t) => s + Math.abs(a.big5[t] - b.big5[t]), 0) / 5);
    comps.push({ key: "personality", s: clamp01(0.7 * pos + 0.3 * sim), label: "Carattere", text: "Indole collaborativa e stabile" });
  }

  // --- Aggregazione: media geometrica pesata (a fasce su effect-size) ---
  let wsum = 0, lnsum = 0;
  comps.forEach(c => { const w = TIERS[c.key] || 1; const s = Math.max(0.05, Math.min(1, c.s)); wsum += w; lnsum += w * Math.log(s); });
  let geo = wsum ? Math.exp(lnsum / wsum) : 0.5;
  // Veto dealbreaker: obiettivi opposti abbassano (non azzerano)
  if (warn.some(w => w.startsWith("Obiettivi"))) geo *= 0.72;

  const score = Math.max(40, Math.min(98, Math.round(40 + 58 * geo)));
  const parts = comps.map(c => ({ key: c.key, label: c.label, pct: Math.round(c.s * 100), text: c.text })).sort((x, y) => y.pct - x.pct);

  // Profondità del profilo (quanti blocchi psicometrici condivisi)
  const blocks = ["values", "goal", "reliability", "role", "personality"].filter(k => parts.some(p => p.key === k)).length;
  const depth = blocks >= 5 ? "Completo" : blocks >= 3 ? "Approfondito" : blocks >= 1 ? "Buono" : "Base";

  return { score, parts, warn, insight: buildInsight(A, B, comps, taste), depth };
}

// --- Testi delle componenti (specifici e falsificabili, anti-Barnum) ---
function topSharedValue(av, bv) {
  let best = null, bestScore = -Infinity;
  VALUE_KEYS.forEach(k => { const both = Math.min(av[k], bv[k]); if (av[k] > 0.3 && bv[k] > 0.3 && both > bestScore) { bestScore = both; best = k; } });
  return best;
}
function valuesText(av, bv, r) {
  const k = topSharedValue(av, bv);
  if (k) return `Stesso valore guida: ${k.toLowerCase()}`;
  return r >= 0 ? "Sistemi di valori compatibili" : "Valori piuttosto diversi";
}
function goalText(g1, g2) {
  const lvl = ["hobby", "hobby+", "equilibrio", "semi-pro", "professione"];
  return Math.abs(g1 - g2) <= 1 ? `Stessa ambizione: ${lvl[Math.max(0, Math.min(4, Math.round((g1 + g2) / 2) - 1))]}` : "Ambizioni un po' diverse";
}
function tasteText(t) {
  if (t.songs.length) return `${t.songs.length} brano${t.songs.length > 1 ? "i" : ""} in comune: ${t.songs.join(", ")}`;
  if (t.genres.length) return `Generi in comune: ${t.genres.join(", ")}`;
  return "Pochi gusti in comune";
}
function roleText(ia, ib) {
  if (ia.D * ib.D < -0.04) return "Uno tende a guidare, l'altro a sostenere: ruoli che si incastrano";
  if (ia.D > 0.2 && ib.D > 0.2) return "Entrambi leader: attenzione a chi prende le decisioni";
  return "Ruoli equilibrati";
}

// --- Insight "sorprendente" (serendipity), specifico e falsificabile ---
function buildInsight(A, B, comps, taste) {
  const a = A.deep || {}, b = B.deep || {}, name = (B.name || "").split(" ")[0] || "voi";
  // 1) valore condiviso NON ovvio (inferito dal test, non dichiarato)
  if (a.values && b.values) {
    const k = topSharedValue(a.values, b.values);
    if (k) return { kind: "valore", text: `Oltre alla musica condividete un valore profondo: ${k.toLowerCase()}. Spesso è ciò che tiene insieme un gruppo nel tempo.` };
  }
  // 2) complementarità di ruolo (differenza vista come risorsa)
  if (a.ipc && b.ipc && a.ipc.D * b.ipc.D < -0.06) {
    const leader = a.ipc.D > b.ipc.D ? "tu guidi" : `${name} guida`;
    return { kind: "ruolo", text: `Vi completate: ${leader} e l'altro/a sostiene. Un equilibrio che funziona, se il rispetto è reciproco.` };
  }
  // 3) brano in comune (relevance concreta)
  if (taste.songs.length) return { kind: "brano", text: `Sapete entrambi “${taste.songs[0]}”: potreste suonarla già alla prima prova.` };
  // 4) stessa ambizione
  if (a.goal != null && b.goal != null && Math.abs(a.goal - b.goal) <= 1)
    return { kind: "obiettivo", text: `Avete la stessa idea di dove volete arrivare con la musica: raro e prezioso.` };
  if (taste.genres.length) return { kind: "genere", text: `Stessa zona musicale (${taste.genres.join(", ")}): buon punto di partenza per una jam.` };
  return null;
}

window.JamAffinity = { IPIP_ITEMS, VALUE_ITEMS, VALUE_KEYS, IPC_ITEMS, BUSSOLA, scoreBig5, scoreValues, scoreIPC, computeAffinity };
