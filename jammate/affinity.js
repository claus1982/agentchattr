/* JamMate — Affinity Engine ("Sintonia")
 * ---------------------------------------------------------------------------
 * Modulo ISOLATO e riusabile. Due strati ben separati:
 *   1) CORE generico  -> media pesata di componenti di similarità/complementarità
 *   2) CONFIG musicale -> domande della "Bussola", strumenti psicometrici, pesi
 * Per estrarlo come servizio/SaaS in futuro basta cambiare la CONFIG.
 *
 * Fondamento scientifico (vedi MATCHING_AVANZATO.md):
 *  - Big Five (Mini-IPIP, dominio pubblico) — NON MBTI
 *  - Similarità su valori/obiettivi; complementarità sui ruoli (Montoya 2008)
 *  - Affidabilità/Coscienziosità = "anello debole" (Bell 2007)
 *  - Gusto/repertorio condivisi creano legame via valori (Boer 2011)
 *  - CAVEAT: la "chimica" è quasi impredicibile (Joel/Finkel) -> punteggio
 *    SOFT + spiegazione, mai una promessa.
 * =========================================================================== */

// ---- CONFIG: Mini-IPIP (20 item, dominio pubblico, Donnellan et al. 2006) ----
// trait: O/C/E/A/N ; rev: item invertito (punteggio = 6 - risposta)
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

// ---- CONFIG: "Bussola del musicista" (custom, parte band-specifica) ----
// Ogni domanda è una scala 1..5 con etichette ai due estremi.
const BUSSOLA = [
  { id: "goal",    q: "Cosa cerchi dalla musica?",            lo: "Puro divertimento", hi: "Diventare professionista" },
  { id: "orig",    q: "Originali o cover?",                   lo: "Solo cover",         hi: "Solo brani originali" },
  { id: "improv",  q: "Come ti piace suonare?",               lo: "Tutto preparato",    hi: "Tanta improvvisazione" },
  { id: "rehear",  q: "Quanto vuoi provare?",                 lo: "Saltuariamente",     hi: "Più volte a settimana" },
  { id: "energy",  q: "Che energia preferisci?",              lo: "Calma / acustica",   hi: "Intensa / potente" },
  { id: "reliab",  q: "Quanto sei affidabile e puntuale?",    lo: "Vado a sensazione",  hi: "Estremamente affidabile" },
  { id: "reliabW", q: "Quanto conta per te l'affidabilità altrui?", lo: "Poco",         hi: "Tantissimo" }
];

// Pesi del punteggio soft (sommano ~1). Modificabili senza toccare il core.
const AFFINITY_WEIGHTS = {
  goal: 0.26,          // similarità obiettivi/impegno (predittore più forte)
  taste: 0.22,         // gusto + repertorio condivisi (legame via valori)
  reliability: 0.16,   // affidabilità "anello debole"
  style: 0.18,         // originali/cover + improvvisazione + energia
  complement: 0.08,    // ruoli/strumenti complementari
  personality: 0.10    // trio "andare d'accordo" + similarità (effetti modesti)
};

// =========================== CORE GENERICO =================================
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const sim5 = (a, b) => 1 - Math.abs(a - b) / 4;          // similarità su scala 1..5
const norm5 = (x) => (x - 1) / 4;                         // 1..5 -> 0..1

// Calcola i Big Five (0..1 per tratto) dalle 20 risposte Mini-IPIP (array 1..5)
function scoreBig5(answers) {
  const acc = { O: [], C: [], E: [], A: [], N: [] };
  IPIP_ITEMS.forEach((it, i) => {
    const r = answers[i] || 3;
    acc[it.t].push(it.rev ? 6 - r : r);
  });
  const out = {};
  for (const t in acc) out[t] = norm5(acc[t].reduce((s, v) => s + v, 0) / acc[t].length);
  return out; // {O,C,E,A,N} in 0..1
}

// Overlap gusti/repertorio fra due profili base (0..1)
function tasteOverlap(a, b) {
  const ga = a.genres || [], gb = b.genres || [];
  const gShared = ga.filter(g => gb.includes(g)).length;
  const gScore = ga.length && gb.length ? gShared / Math.min(ga.length, gb.length) : 0;
  const ra = (a.repertoire || []).map(r => r.title.toLowerCase());
  const rb = (b.repertoire || []).map(r => r.title.toLowerCase());
  const songs = ra.filter(t => rb.includes(t)).length;
  const sScore = clamp01(songs / 3); // 3+ brani in comune = pieno
  return { score: clamp01(0.55 * gScore + 0.45 * sScore), shared: gShared, songs };
}

/* computeAffinity(profA, profB)
 * profX = profilo completo con .genres .repertoire .instruments .deep
 * Richiede che entrambi abbiano deep.done === true.
 * Ritorna { score (0..100), parts:[{key,label,pct,text}], warn:[...] } */
function computeAffinity(A, B) {
  const a = A.deep, b = B.deep;
  const warn = [];

  // 1) Obiettivi/impegno (similarità)
  const goal = sim5(a.goal, b.goal);
  if (Math.abs(a.goal - b.goal) >= 3) warn.push("Obiettivi molto diversi (hobby vs professione)");

  // 2) Gusto + repertorio
  const taste = tasteOverlap(A, B);

  // 3) Affidabilità ("anello debole" = il minore dei due)
  const reliability = norm5(Math.min(a.reliab, b.reliab));
  // se uno tiene molto all'affidabilità e l'altro è poco affidabile -> avviso
  if ((a.reliabW >= 4 && b.reliab <= 2) || (b.reliabW >= 4 && a.reliab <= 2))
    warn.push("Possibile attrito sull'affidabilità");

  // 4) Stile (originali/cover + improvvisazione + energia)
  const style = (sim5(a.orig, b.orig) + sim5(a.improv, b.improv) + sim5(a.energy, b.energy)) / 3;

  // 5) Complementarità di strumento (ruoli diversi = utile)
  const iA = (A.instruments || [])[0], iB = (B.instruments || [])[0];
  const complement = iA && iB ? (iA === iB ? 0.4 : 1) : 0.6;

  // 6) Personalità: trio "andare d'accordo" (A alta, C alta, N bassa) + similarità valori
  const trio = ((a.big5.A + b.big5.A) / 2 + (a.big5.C + b.big5.C) / 2 + (1 - (a.big5.N + b.big5.N) / 2)) / 3;
  const big5sim = 1 - (["O", "C", "E", "A", "N"].reduce((s, t) => s + Math.abs(a.big5[t] - b.big5[t]), 0) / 5);
  const personality = 0.6 * trio + 0.4 * big5sim;

  const W = AFFINITY_WEIGHTS;
  const raw =
    W.goal * goal + W.taste * taste.score + W.reliability * reliability +
    W.style * style + W.complement * complement + W.personality * personality;

  // 38..99 per evitare zeri scoraggianti e "100% garantito"
  const score = Math.max(38, Math.min(99, Math.round(raw * 100)));

  const parts = [
    { key: "goal", label: "Obiettivi affini", pct: Math.round(goal * 100), text: goalText(a.goal, b.goal) },
    { key: "taste", label: "Gusti & repertorio", pct: Math.round(taste.score * 100), text: tasteText(taste) },
    { key: "reliability", label: "Affidabilità", pct: Math.round(reliability * 100), text: "Entrambi puntate sulla serietà" },
    { key: "style", label: "Modo di suonare", pct: Math.round(style * 100), text: "Approccio compatibile (cover/originali, prove, energia)" },
    { key: "complement", label: "Ruoli complementari", pct: Math.round(complement * 100), text: iA && iB && iA !== iB ? `${iA} + ${iB} si incastrano` : "Stesso strumento" },
    { key: "personality", label: "Carattere", pct: Math.round(personality * 100), text: "Indole collaborativa" }
  ].sort((x, y) => y.pct - x.pct);

  return { score, parts, warn };
}

function goalText(g1, g2) {
  const lvl = ["hobby", "hobby+", "equilibrio", "semi-pro", "professione"];
  const i = Math.round((g1 + g2) / 2) - 1;
  return Math.abs(g1 - g2) <= 1 ? `Stessa visione: ${lvl[Math.max(0, Math.min(4, i))]}` : "Visioni un po' diverse";
}
function tasteText(t) {
  if (t.songs) return `${t.songs} brano${t.songs > 1 ? "i" : ""} in comune nel repertorio`;
  if (t.shared) return `${t.shared} generi in comune`;
  return "Pochi gusti in comune";
}

// Espone in globale (no build step)
window.JamAffinity = { IPIP_ITEMS, BUSSOLA, scoreBig5, computeAffinity };
