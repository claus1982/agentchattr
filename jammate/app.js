/* JamMate — logica dell'app (prototipo MVP).
 * Single-page app in JavaScript puro, senza framework e senza build step:
 * basta aprire index.html. I dati persistono nel browser (localStorage). */

// ---------- Stato & persistenza ----------
const STORE_KEY = "jammate_state_v2";

function loadState() {
  const raw = localStorage.getItem(STORE_KEY);
  if (raw) { try { return migrate(JSON.parse(raw)); } catch (e) { /* fallthrough */ } }
  return freshState();
}
function freshState() {
  return {
    profiles: SEED_PROFILES, events: SEED_EVENTS, messages: SEED_MESSAGES,
    me: {
      id: "me", name: "", avatar: "🎵", color: GRADS[0], city: "Milano", distanceKm: 0,
      instruments: [], level: "Intermedio", genres: [], bio: "", tagline: "",
      links: { youtube: "", spotify: "", instagram: "" },
      repertoire: [], endo: { puntualita: 0, tecnica: 0, attitudine: 0 }
    },
    liked: [], passed: [], matches: ["u2"],
    filters: { instrument: "", level: "", genre: "", distance: 30 },
    ui: { discoverMode: "match", unread: false },
    onboarded: false
  };
}
function migrate(s) { const base = freshState(); return Object.assign(base, s, { ui: Object.assign(base.ui, s.ui || {}) }); }

let state = loadState();
function save() { localStorage.setItem(STORE_KEY, JSON.stringify(state)); }

// ---------- Utility ----------
const $ = (sel, root = document) => root.querySelector(sel);
const el = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hash = (s) => { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h; };

function toast(msg) {
  const t = el(`<div class="toast">${esc(msg)}</div>`);
  document.body.appendChild(t); setTimeout(() => t.remove(), 2200);
}
function options(list, selected, placeholder) {
  let o = placeholder ? `<option value="">${esc(placeholder)}</option>` : "";
  return o + list.map(v => `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(v)}</option>`).join("");
}
function chips(list, selected) {
  return list.map(v => `<span class="chip${selected.includes(v) ? " on" : ""}" data-chip="${esc(v)}">${esc(v)}</span>`).join("");
}
function toggleChip(node, arr) { const v = node.dataset.chip, i = arr.indexOf(v); if (i >= 0) arr.splice(i, 1); else arr.push(v); node.classList.toggle("on"); }
function avgScore(e) { return Math.round((e.puntualita + e.tecnica + e.attitudine) / 3); }
function endoBlock(e) {
  return `<div class="endo">${[["Puntualità", e.puntualita], ["Tecnica", e.tecnica], ["Attitudine", e.attitudine]].map(([l, n]) => `
    <span class="lbl">${l}</span><span class="num">${n}%</span>
    <div class="bar" style="grid-column:1/-1"><i style="width:${n}%"></i></div>`).join("")}</div>`;
}
function formatDate(iso) {
  try { return new Date(iso + "T00:00:00").toLocaleDateString("it-IT", { weekday: "short", day: "numeric", month: "long" }); }
  catch (e) { return iso; }
}

// ---------- Compatibilità (l'idea distintiva: brani in comune) ----------
function sharedGenres(p) { return p.genres.filter(g => state.me.genres.includes(g)); }
function sharedSongs(p) {
  const mine = state.me.repertoire.map(r => r.title.toLowerCase());
  return p.repertoire.filter(r => mine.includes(r.title.toLowerCase()));
}
function compatibility(p) {
  let s = 46;
  s += sharedGenres(p).length * 9;
  s += sharedSongs(p).length * 13;
  s += Math.max(0, 15 - p.distanceKm);
  s += Math.round(avgScore(p.endo) / 12);
  if (!state.me.genres.length && !state.me.repertoire.length) s += hash(p.id) % 16;
  return Math.max(38, Math.min(99, Math.round(s)));
}
function commonText(p) {
  const g = sharedGenres(p), so = sharedSongs(p);
  if (so.length) return `🎵 ${so.length} brano${so.length > 1 ? "i" : ""} in comune: ${so.map(x => x.title).join(", ")}`;
  if (g.length) return `🎯 Generi in comune: ${g.join(", ")}`;
  return `📍 A ${p.distanceKm} km da te`;
}

// ---------- Router ----------
let currentView = "discover";
function navigate(view) {
  stopMetronome(); stopTuner();
  currentView = view;
  if (view === "messages") { state.ui.unread = false; save(); }
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.view === view));
  render();
}
function render() {
  const app = $("#app"); app.innerHTML = "";
  updateChatDot();
  if (!state.onboarded) return renderOnboarding(app);
  ({ discover: renderDiscover, board: renderBoard, messages: renderMessages, tools: renderTools, profile: renderProfile }[currentView] || renderDiscover)(app);
}
function updateChatDot() { const d = $("#chatDot"); if (d) d.hidden = !state.ui.unread; }

// ---------- Onboarding ----------
function renderOnboarding(app) {
  app.appendChild(el(`
    <div>
      <h1 class="view-title">Benvenuto su JamMate 🎶</h1>
      <p class="view-sub">Trova musicisti vicino a te e suona insieme dal vivo. Crea il tuo profilo in 30 secondi.</p>
      <div class="card flat">
        <label class="field">Come ti chiami (o nome d'arte)</label>
        <input type="text" id="obName" placeholder="Es. Marco / DJ Sonic" />
        <label class="field" style="margin-top:12px">La tua città</label>
        <input type="text" id="obCity" value="Milano" />
        <label class="field" style="margin-top:12px">Strumenti che suoni</label>
        <div class="chips" id="obInstruments">${chips(INSTRUMENTS, [])}</div>
        <label class="field" style="margin-top:12px">Livello</label>
        <select id="obLevel">${options(LEVELS, "Intermedio")}</select>
        <label class="field" style="margin-top:12px">Generi preferiti</label>
        <div class="chips" id="obGenres">${chips(GENRES, [])}</div>
        <button class="btn" id="obDone" style="margin-top:18px">Crea il mio profilo →</button>
      </div>
    </div>`));
  const selIns = [], selGen = [];
  app.querySelectorAll("#obInstruments .chip").forEach(c => c.onclick = () => toggleChip(c, selIns));
  app.querySelectorAll("#obGenres .chip").forEach(c => c.onclick = () => toggleChip(c, selGen));
  $("#obDone").onclick = () => {
    const name = $("#obName").value.trim();
    if (!name) return toast("Inserisci almeno il nome");
    Object.assign(state.me, {
      name, city: $("#obCity").value.trim() || "Milano",
      avatar: ["🎸", "🎤", "🥁", "🎹", "🎻", "🎷"][Math.floor(Math.random() * 6)],
      color: GRADS[Math.floor(Math.random() * GRADS.length)],
      instruments: selIns, level: $("#obLevel").value, genres: selGen
    });
    state.onboarded = true; save();
    toast("Profilo creato! Scorri per trovare musicisti 🔥");
    navigate("discover");
  };
}

// ---------- Vista: Scopri ----------
function renderDiscover(app) {
  app.appendChild(el(`
    <div>
      <h1 class="view-title">Scopri musicisti</h1>
      <div class="segmented">
        <button data-mode="match" class="${state.ui.discoverMode === "match" ? "on" : ""}">🔥 Match</button>
        <button data-mode="search" class="${state.ui.discoverMode === "search" ? "on" : ""}">🔍 Cerca con filtri</button>
      </div>
      <div id="discBody"></div>
    </div>`));
  app.querySelectorAll(".segmented button").forEach(b => b.onclick = () => {
    state.ui.discoverMode = b.dataset.mode; save(); renderDiscover2();
  });
  if (state.ui.discoverMode === "match") renderSwipe($("#discBody"));
  else renderSearch($("#discBody"));
}

function getDeck() {
  const f = state.filters;
  return state.profiles.filter(p =>
    !state.liked.includes(p.id) && !state.passed.includes(p.id) &&
    (!f.instrument || p.instruments.includes(f.instrument)) &&
    (!f.level || p.level === f.level) &&
    (!f.genre || p.genres.includes(f.genre)) &&
    p.distanceKm <= f.distance
  );
}

function renderSwipe(box) {
  const deck = getDeck();
  if (!deck.length) {
    box.innerHTML = `<div class="empty">Hai visto tutti i musicisti con questi filtri! 🎉<br>Allarga la ricerca o riparti.</div>`;
    const b = el(`<button class="btn secondary" style="margin-top:8px">↺ Rivedi i profili scartati</button>`);
    b.onclick = () => { state.passed = []; save(); renderDiscover2(); };
    box.appendChild(b);
    box.appendChild(filterButton());
    return;
  }
  const wrap = el(`<div><div class="deck" id="deck"></div>
    <div class="deck-actions">
      <button class="round-btn pass" id="btnPass" title="Passa">✕</button>
      <button class="round-btn info" id="btnInfo" title="Dettagli">ℹ️</button>
      <button class="round-btn like" id="btnLike" title="Connetti">♥</button>
    </div></div>`);
  box.appendChild(wrap);
  box.appendChild(filterButton());
  const top = deck[0];
  $("#deck").appendChild(swipeCard(top));
  $("#btnPass").onclick = () => decide(top, "pass");
  $("#btnLike").onclick = () => decide(top, "like");
  $("#btnInfo").onclick = () => openProfileSheet(top);
}
function renderDiscover2() { $("#app").innerHTML = ""; renderDiscover($("#app")); }

function filterButton() {
  const f = state.filters;
  const active = [f.instrument, f.level, f.genre].filter(Boolean).length + (f.distance < 30 ? 1 : 0);
  const b = el(`<button class="btn secondary" style="margin-top:14px">⚙️ Filtri${active ? ` · ${active} attivi` : ""}</button>`);
  b.onclick = openFilterSheet;
  return b;
}

function swipeCard(p) {
  const card = el(`
    <div class="swipe-card" data-id="${p.id}">
      <div class="stamp like">JAM!</div>
      <div class="stamp nope">NO</div>
      <div class="hero" style="background:${p.color}">
        <div class="big-emoji">${p.avatar}</div>
        <div class="compat">⚡ ${compatibility(p)}%</div>
      </div>
      <div class="body">
        <div class="name">${esc(p.name)} <span class="score">★ ${avgScore(p.endo)}</span></div>
        <div class="loc">📍 ${esc(p.city)} · ${p.distanceKm} km · ${esc(p.level)}</div>
        <div class="tagline">“${esc(p.tagline || "")}”</div>
        <div class="tags">
          ${p.instruments.map(i => `<span class="tag accent">${esc(i)}</span>`).join("")}
          ${p.genres.map(g => `<span class="tag">${esc(g)}</span>`).join("")}
        </div>
        <div class="common">${esc(commonText(p))}</div>
      </div>
    </div>`);
  attachDrag(card, p);
  return card;
}

function attachDrag(card, p) {
  let startX = 0, startY = 0, dx = 0, dragging = false;
  const like = card.querySelector(".stamp.like"), nope = card.querySelector(".stamp.nope");
  const down = (e) => {
    if (e.target.closest(".body") && e.target.closest(".body").scrollHeight > e.target.closest(".body").clientHeight && e.type === "pointerdown") { /* allow scroll */ }
    dragging = true; startX = e.clientX; startY = e.clientY; card.style.transition = "none"; card.setPointerCapture && card.setPointerCapture(e.pointerId);
  };
  const move = (e) => {
    if (!dragging) return;
    dx = e.clientX - startX; const dy = e.clientY - startY;
    if (Math.abs(dy) > Math.abs(dx) * 1.5 && Math.abs(dx) < 12) return; // scroll verticale
    card.style.transform = `translate(${dx}px, ${dy * 0.2}px) rotate(${dx / 18}deg)`;
    like.style.opacity = dx > 0 ? Math.min(1, dx / 90) : 0;
    nope.style.opacity = dx < 0 ? Math.min(1, -dx / 90) : 0;
  };
  const up = () => {
    if (!dragging) return; dragging = false; card.style.transition = "transform .3s ease";
    if (dx > 120) return flyOut(card, 1, () => decide(p, "like", true));
    if (dx < -120) return flyOut(card, -1, () => decide(p, "pass", true));
    card.style.transform = ""; like.style.opacity = 0; nope.style.opacity = 0; dx = 0;
  };
  card.addEventListener("pointerdown", down);
  card.addEventListener("pointermove", move);
  card.addEventListener("pointerup", up);
  card.addEventListener("pointercancel", up);
}
function flyOut(card, dir, done) {
  card.style.transition = "transform .35s ease, opacity .35s ease";
  card.style.transform = `translate(${dir * 700}px, -40px) rotate(${dir * 30}deg)`;
  card.style.opacity = "0";
  setTimeout(done, 280);
}

function decide(p, action, skipAnim) {
  if (action === "like") {
    if (!state.liked.includes(p.id)) state.liked.push(p.id);
    const matched = Math.random() < (0.42 + compatibility(p) / 200);
    if (matched && !state.matches.includes(p.id)) {
      state.matches.push(p.id);
      if (!state.messages[p.id]) state.messages[p.id] = [{ from: "them", text: opener(p) }];
      state.ui.unread = true; save(); showMatch(p); return;
    }
  } else {
    if (!state.passed.includes(p.id)) state.passed.push(p.id);
  }
  save();
  // anima la carta corrente se non già fatto, poi prossima
  if (!skipAnim) {
    const card = $(".swipe-card");
    if (card) return flyOut(card, action === "like" ? 1 : -1, () => renderDiscover2());
  }
  renderDiscover2();
}
function opener(p) {
  const lines = [
    `Ciao! Ho visto che suoni ${p.instruments[0].toLowerCase()}, ci organizziamo per una prova?`,
    `Ehi! Bel profilo, che ne dici di una jam questa settimana?`,
    `Ciao 🤘 cerchi una band attiva? Parliamone!`
  ];
  return lines[hash(p.id) % lines.length];
}

function showMatch(p) {
  const ov = el(`
    <div class="match-overlay">
      <div>
        <h2>È un match! 🎉</h2>
        <p class="view-sub">Tu e ${esc(p.name.split(" ")[0])} volete suonare insieme.</p>
        <div class="match-avatars">
          <div class="avatar lg" style="background:${state.me.color}">${state.me.avatar}</div>
          <div class="avatar lg" style="background:${p.color}">${p.avatar}</div>
        </div>
        <div style="max-width:320px;margin:0 auto">
          <button class="btn" id="mChat">💬 Scrivi a ${esc(p.name.split(" ")[0])}</button>
          <button class="btn secondary" id="mKeep" style="margin-top:10px">Continua a scorrere</button>
        </div>
      </div>
    </div>`);
  document.body.appendChild(ov);
  $("#mKeep").onclick = () => { ov.remove(); renderDiscover2(); };
  $("#mChat").onclick = () => { ov.remove(); navigate("messages"); setTimeout(() => openChat(p), 50); };
}

// ---------- Ricerca con filtri (lista) ----------
function renderSearch(box) {
  const f = state.filters;
  box.appendChild(el(`
    <div class="filters">
      <div class="filter-row">
        <div><label class="field">Strumento</label><select id="fIns">${options(INSTRUMENTS, f.instrument, "Tutti")}</select></div>
        <div><label class="field">Livello</label><select id="fLvl">${options(LEVELS, f.level, "Tutti")}</select></div>
      </div>
      <div class="filter-row">
        <div><label class="field">Genere</label><select id="fGen">${options(GENRES, f.genre, "Tutti")}</select></div>
        <div><label class="field">Distanza max: <span class="range-val" id="fDistVal">${f.distance} km</span></label>
          <input type="range" id="fDist" min="1" max="50" value="${f.distance}" /></div>
      </div>
    </div>
    <div id="results"></div>`));
  $("#fIns").onchange = e => { f.instrument = e.target.value; save(); paintResults(); };
  $("#fLvl").onchange = e => { f.level = e.target.value; save(); paintResults(); };
  $("#fGen").onchange = e => { f.genre = e.target.value; save(); paintResults(); };
  $("#fDist").oninput = e => { f.distance = +e.target.value; $("#fDistVal").textContent = f.distance + " km"; };
  $("#fDist").onchange = () => { save(); paintResults(); };
  paintResults();
}
function matchProfiles() {
  const f = state.filters;
  return state.profiles.filter(p =>
    (!f.instrument || p.instruments.includes(f.instrument)) &&
    (!f.level || p.level === f.level) &&
    (!f.genre || p.genres.includes(f.genre)) &&
    p.distanceKm <= f.distance
  ).sort((a, b) => compatibility(b) - compatibility(a));
}
function paintResults() {
  const box = $("#results"); if (!box) return;
  const list = matchProfiles();
  if (!list.length) { box.innerHTML = `<div class="empty">Nessun musicista con questi filtri. Allarga la distanza o togli un filtro.</div>`; return; }
  box.innerHTML = `<p class="view-sub">${list.length} risultat${list.length === 1 ? "o" : "i"} · ordinati per compatibilità</p>`;
  list.forEach(p => box.appendChild(profileCard(p)));
}
function profileCard(p) {
  const c = el(`
    <div class="card">
      <div class="card-head">
        <div class="avatar" style="background:${p.color}">${p.avatar}</div>
        <div class="meta">
          <div class="name">${esc(p.name)} <span class="score">★ ${avgScore(p.endo)}</span></div>
          <div class="loc">📍 ${esc(p.city)} · ${p.distanceKm} km · ${esc(p.level)}</div>
        </div>
        <div class="compat-mini" style="font-weight:800;color:var(--accent)">⚡${compatibility(p)}%</div>
      </div>
      <div class="tags">
        ${p.instruments.map(i => `<span class="tag accent">${esc(i)}</span>`).join("")}
        ${p.genres.slice(0, 3).map(g => `<span class="tag">${esc(g)}</span>`).join("")}
      </div>
      <div class="tags" style="margin-top:6px"><span class="dist">🎵 ${p.repertoire.length} brani · ${esc(commonText(p))}</span></div>
    </div>`);
  c.onclick = () => openProfileSheet(p);
  return c;
}

// ---------- Sheet: filtri (dalla modalità swipe) ----------
function openFilterSheet() {
  const f = state.filters;
  openModal(`
    <h2>Filtri di ricerca</h2>
    <p class="view-sub">Restringi chi vedi nel mazzo.</p>
    <label class="field">Strumento</label><select id="sfIns">${options(INSTRUMENTS, f.instrument, "Tutti")}</select>
    <label class="field" style="margin-top:10px">Livello</label><select id="sfLvl">${options(LEVELS, f.level, "Tutti")}</select>
    <label class="field" style="margin-top:10px">Genere</label><select id="sfGen">${options(GENRES, f.genre, "Tutti")}</select>
    <label class="field" style="margin-top:10px">Distanza max: <span class="range-val" id="sfDistVal">${f.distance} km</span></label>
    <input type="range" id="sfDist" min="1" max="50" value="${f.distance}">
    <button class="btn" id="sfApply" style="margin-top:18px">Applica</button>
    <button class="btn secondary" id="sfClear" style="margin-top:10px">Azzera filtri</button>
  `);
  $("#sfDist").oninput = e => $("#sfDistVal").textContent = e.target.value + " km";
  $("#sfApply").onclick = () => {
    f.instrument = $("#sfIns").value; f.level = $("#sfLvl").value; f.genre = $("#sfGen").value; f.distance = +$("#sfDist").value;
    save(); closeModal(); renderDiscover2();
  };
  $("#sfClear").onclick = () => { state.filters = { instrument: "", level: "", genre: "", distance: 30 }; save(); closeModal(); renderDiscover2(); };
}

// ---------- Sheet: dettaglio profilo ----------
function openProfileSheet(p) {
  const links = Object.entries(p.links).filter(([, v]) => v);
  const matched = state.matches.includes(p.id);
  openModal(`
    <div style="text-align:center">
      <div class="avatar lg" style="margin:0 auto;background:${p.color}">${p.avatar}</div>
      <h2>${esc(p.name)}</h2>
      <div class="loc">📍 ${esc(p.city)} · ${p.distanceKm} km · ${esc(p.level)} · <span class="score">★ ${avgScore(p.endo)}</span></div>
      <div style="margin-top:6px;font-weight:800;color:var(--accent)">⚡ ${compatibility(p)}% compatibilità</div>
    </div>
    <div class="tags" style="justify-content:center;margin-top:10px">
      ${p.instruments.map(i => `<span class="tag accent">${esc(i)}</span>`).join("")}
      ${p.genres.map(g => `<span class="tag">${esc(g)}</span>`).join("")}
    </div>
    ${p.bio ? `<div class="section-label">Bio</div><p style="margin:0;line-height:1.5">${esc(p.bio)}</p>` : ""}
    ${links.length ? `<div class="section-label">Ascolta</div><div class="linkrow">${links.map(([k, v]) => `<a href="${esc(v)}" target="_blank" rel="noopener">${({ youtube: "▶ YouTube", spotify: "♫ Spotify", instagram: "◎ Instagram" })[k] || k}</a>`).join("")}</div>` : ""}
    <div class="section-label">Repertorio & tonalità</div>
    ${p.repertoire.length ? p.repertoire.map(r => `
      <div class="rep-item"><div><div class="song">${esc(r.title)}</div><div class="artist">${esc(r.artist || "")}</div></div>
        <span class="key-badge">${esc(r.key)}</span></div>`).join("") : `<p class="view-sub">Nessun brano indicato.</p>`}
    <div class="section-label">Reputazione</div>
    ${endoBlock(p.endo)}
    <div style="margin-top:22px"><button class="btn" id="contactBtn">💬 ${matched ? "Scrivi a" : "Contatta"} ${esc(p.name.split(" ")[0])}</button></div>
  `);
  $("#contactBtn").onclick = () => {
    if (!state.matches.includes(p.id)) { state.matches.push(p.id); if (!state.messages[p.id]) state.messages[p.id] = []; save(); }
    closeModal(); navigate("messages"); setTimeout(() => openChat(p), 50);
  };
}

// ---------- Vista: Bacheca ----------
function renderBoard(app) {
  app.appendChild(el(`
    <div>
      <div class="row-between"><h1 class="view-title">Bacheca annunci</h1>
      <button class="btn small" id="newAd">＋ Nuovo</button></div>
      <p class="view-sub">Band in cerca di membri e jam vicino a te. Candidati agli slot liberi.</p>
      <div id="eventList"></div>
    </div>`));
  $("#newAd").onclick = openCreateSheet;
  const box = $("#eventList");
  if (!state.events.length) return box.innerHTML = `<div class="empty">Ancora nessun annuncio. Creane uno con ＋ Nuovo</div>`;
  state.events.forEach(ev => box.appendChild(eventCard(ev)));
}
function eventCard(ev) {
  const open = ev.slots.filter(s => !s.filled).length;
  const c = el(`
    <div class="card">
      <div class="row-between"><span class="event-date">📅 ${formatDate(ev.date)}</span>
        ${open ? `<span class="badge-new">${open} slot liber${open === 1 ? "o" : "i"}</span>` : ""}</div>
      <div style="font-weight:700;font-size:1.08rem;margin:6px 0 2px">${esc(ev.title)}</div>
      <div class="loc">${ev.authorAvatar} ${esc(ev.author)} · 📍 ${esc(ev.city)} · ${ev.distanceKm} km</div>
      <div class="tags" style="margin-top:8px">${ev.genres.map(g => `<span class="tag">${esc(g)}</span>`).join("")}</div>
      <div class="slot-row">${ev.slots.map((s, i) => `<span class="slot ${s.filled ? "filled" : "open"}" data-slot="${i}">${s.filled ? "✓" : "+"} ${esc(s.instrument)}</span>`).join("")}</div>
    </div>`);
  c.onclick = () => openEventSheet(ev);
  return c;
}
function openEventSheet(ev) {
  openModal(`
    <span class="event-date">📅 ${formatDate(ev.date)}</span>
    <h2>${esc(ev.title)}</h2>
    <div class="loc">${ev.authorAvatar} ${esc(ev.author)} · 📍 ${esc(ev.city)} · ${ev.distanceKm} km</div>
    <div class="tags" style="margin-top:8px">${ev.genres.map(g => `<span class="tag">${esc(g)}</span>`).join("")}</div>
    <div class="section-label">Descrizione</div><p style="margin:0;line-height:1.5">${esc(ev.description)}</p>
    <div class="section-label">Slot strumenti</div><div id="slotList"></div>`);
  const sl = $("#slotList");
  ev.slots.forEach((s) => {
    const row = el(`<div class="rep-item">
      <span class="song">${s.filled ? "✓" : "🔎"} ${esc(s.instrument)}</span>
      ${s.filled ? `<span class="tag lvl">Occupato</span>` : `<button class="btn small" data-apply="1">Candidati</button>`}</div>`);
    const btn = row.querySelector("[data-apply]");
    if (btn) btn.onclick = () => { s.filled = true; s.applicant = state.me.name; save(); toast(`Candidatura inviata: ${s.instrument} 🎉`); closeModal(); renderBoard2(); };
    sl.appendChild(row);
  });
}
function renderBoard2() { if (currentView === "board") { $("#app").innerHTML = ""; renderBoard($("#app")); } }

function openCreateSheet() {
  openModal(`
    <h2>Nuovo annuncio 📌</h2>
    <p class="view-sub">Cerchi membri o organizzi una jam? Pubblica qui.</p>
    <label class="field">Titolo</label><input type="text" id="evTitle" placeholder="Es. Cerchiamo bassista rock">
    <label class="field" style="margin-top:10px">Nome band / organizzatore</label><input type="text" id="evAuthor" placeholder="Es. The Riffs" value="${esc(state.me.name)}">
    <div class="filter-row" style="margin-top:10px">
      <div><label class="field">Città</label><input type="text" id="evCity" value="${esc(state.me.city)}"></div>
      <div><label class="field">Data</label><input type="date" id="evDate"></div>
    </div>
    <label class="field" style="margin-top:10px">Generi</label><div class="chips" id="evGenres">${chips(GENRES, [])}</div>
    <label class="field" style="margin-top:10px">Strumenti cercati (slot liberi)</label><div class="chips" id="evSlots">${chips(INSTRUMENTS, [])}</div>
    <label class="field" style="margin-top:10px">Descrizione</label><textarea id="evDesc" placeholder="Dettagli, sala prove, orari…"></textarea>
    <button class="btn" id="evCreate" style="margin-top:18px">Pubblica annuncio</button>`);
  const selGen = [], selSlots = [];
  document.querySelectorAll("#evGenres .chip").forEach(c => c.onclick = () => toggleChip(c, selGen));
  document.querySelectorAll("#evSlots .chip").forEach(c => c.onclick = () => toggleChip(c, selSlots));
  $("#evCreate").onclick = () => {
    const title = $("#evTitle").value.trim();
    if (!title) return toast("Inserisci un titolo");
    if (!selSlots.length) return toast("Seleziona almeno uno strumento cercato");
    state.events.unshift({
      id: "e" + Date.now(), title, author: $("#evAuthor").value.trim() || state.me.name || "Anonimo",
      authorAvatar: state.me.avatar, city: $("#evCity").value.trim() || "Milano", distanceKm: 0,
      date: $("#evDate").value || new Date().toISOString().slice(0, 10),
      genres: selGen, description: $("#evDesc").value.trim(),
      slots: selSlots.map(i => ({ instrument: i, filled: false }))
    });
    save(); closeModal(); toast("Annuncio pubblicato! 📢"); navigate("board");
  };
}

// ---------- Vista: Chat ----------
function renderMessages(app) {
  app.appendChild(el(`<div><h1 class="view-title">Messaggi</h1>
    <p class="view-sub">Accordati senza scambiare il numero di telefono.</p><div id="threads"></div></div>`));
  const box = $("#threads");
  const ids = state.matches.filter(id => state.profiles.find(p => p.id === id));
  if (!ids.length) return box.innerHTML = `<div class="empty">Nessuna conversazione.<br>Fai un <b>match</b> in "Scopri" per iniziare a chattare 🔥</div>`;
  ids.forEach(id => {
    const p = state.profiles.find(x => x.id === id);
    const thread = state.messages[id] || [];
    const last = thread[thread.length - 1];
    const c = el(`<div class="card"><div class="card-head">
      <div class="avatar" style="background:${p.color}">${p.avatar}</div>
      <div class="meta"><div class="name">${esc(p.name)}</div>
      <div class="loc">${last ? esc((last.from === "me" ? "Tu: " : "") + last.text) : "Avete fatto match! Scrivi qualcosa 👋"}</div></div>
    </div></div>`);
    c.onclick = () => openChat(p);
    box.appendChild(c);
  });
}
function openChat(p) {
  if (!state.messages[p.id]) state.messages[p.id] = [];
  openModal(`
    <div class="card-head" style="margin-bottom:12px">
      <div class="avatar" style="background:${p.color}">${p.avatar}</div>
      <div class="meta"><div class="name">${esc(p.name)}</div><div class="loc">📍 ${esc(p.city)} · ${p.distanceKm} km</div></div>
    </div>
    <div class="msg-thread" id="thread"></div>
    <div class="composer"><input type="text" id="msgInput" placeholder="Scrivi un messaggio…" /><button class="btn small" id="sendMsg">Invia</button></div>`);
  paintThread(p);
  const send = () => {
    const v = $("#msgInput").value.trim(); if (!v) return;
    state.messages[p.id].push({ from: "me", text: v }); save(); $("#msgInput").value = ""; paintThread(p);
    setTimeout(() => { state.messages[p.id].push({ from: "them", text: "Perfetto! Organizziamo una prova 🤘" }); save(); paintThread(p); }, 900);
  };
  $("#sendMsg").onclick = send;
  $("#msgInput").addEventListener("keydown", e => { if (e.key === "Enter") send(); });
}
function paintThread(p) {
  const t = $("#thread"); if (!t) return;
  t.innerHTML = state.messages[p.id].map(m => `<div class="bubble ${m.from}">${esc(m.text)}</div>`).join("");
  t.scrollTop = t.scrollHeight;
}

// ---------- Vista: Profilo ----------
function renderProfile(app) {
  const m = state.me;
  app.appendChild(el(`
    <div>
      <div style="text-align:center;margin-bottom:8px">
        <div class="avatar lg" style="margin:0 auto;background:${m.color}">${m.avatar}</div>
        <h1 class="view-title" style="margin-bottom:0">${esc(m.name || "Il mio profilo")}</h1>
        <div class="loc">📍 ${esc(m.city)} · ${esc(m.level)}</div>
      </div>
      <div class="hint">💡 Il tuo <b>repertorio con le tonalità</b> ti rende trovabile e aumenta la compatibilità con chi sa gli stessi brani. È la marcia in più di JamMate.</div>
      <div class="section-label">Repertorio & tonalità</div>
      <div id="myRep"></div>
      <div class="card flat">
        <div class="add-rep">
          <div><label class="field">Brano</label><input type="text" id="repTitle" placeholder="Es. Wonderwall"></div>
          <div><label class="field">Artista</label><input type="text" id="repArtist" placeholder="Es. Oasis"></div>
          <div><label class="field">Tonalità</label><select id="repKey">${options(KEYS, "Do")}</select></div>
          <button class="btn small" id="addRep">Aggiungi</button>
        </div>
      </div>
      <div class="section-label">Frase a effetto</div>
      <input type="text" id="myTag" placeholder="Es. Riff e groove a volontà" value="${esc(m.tagline)}">
      <div class="section-label">Strumenti</div><div class="chips" id="myIns">${chips(INSTRUMENTS, m.instruments)}</div>
      <div class="section-label">Generi</div><div class="chips" id="myGen">${chips(GENRES, m.genres)}</div>
      <div class="section-label">Livello</div><select id="myLvl">${options(LEVELS, m.level)}</select>
      <div class="section-label">Bio</div><textarea id="myBio" placeholder="Racconta chi sei e cosa cerchi…">${esc(m.bio)}</textarea>
      <div class="section-label">Link (per farti ascoltare)</div>
      <input type="text" id="lkYt" placeholder="Link YouTube" value="${esc(m.links.youtube)}" style="margin-bottom:8px">
      <input type="text" id="lkSp" placeholder="Link Spotify" value="${esc(m.links.spotify)}" style="margin-bottom:8px">
      <input type="text" id="lkIg" placeholder="Link Instagram" value="${esc(m.links.instagram)}">
      <button class="btn" id="saveProfile" style="margin-top:20px">Salva profilo</button>
      <button class="btn secondary" id="resetApp" style="margin-top:10px">Azzera dati demo</button>
    </div>`));
  paintMyRep();
  $("#addRep").onclick = () => {
    const title = $("#repTitle").value.trim(); if (!title) return toast("Scrivi il titolo del brano");
    m.repertoire.push({ title, artist: $("#repArtist").value.trim(), key: $("#repKey").value });
    save(); $("#repTitle").value = ""; $("#repArtist").value = ""; paintMyRep(); toast("Brano aggiunto 🎵");
  };
  app.querySelectorAll("#myIns .chip").forEach(c => c.onclick = () => toggleChip(c, m.instruments));
  app.querySelectorAll("#myGen .chip").forEach(c => c.onclick = () => toggleChip(c, m.genres));
  $("#saveProfile").onclick = () => {
    m.tagline = $("#myTag").value.trim(); m.bio = $("#myBio").value.trim(); m.level = $("#myLvl").value;
    m.links = { youtube: $("#lkYt").value.trim(), spotify: $("#lkSp").value.trim(), instagram: $("#lkIg").value.trim() };
    save(); toast("Profilo salvato ✓");
  };
  $("#resetApp").onclick = () => { if (confirm("Azzerare tutti i dati e ripartire dalla demo?")) { localStorage.removeItem(STORE_KEY); state = loadState(); navigate("discover"); } };
}
function paintMyRep() {
  const box = $("#myRep"); if (!box) return;
  if (!state.me.repertoire.length) return box.innerHTML = `<p class="view-sub">Nessun brano ancora. Aggiungine qui sotto 👇</p>`;
  box.innerHTML = "";
  state.me.repertoire.forEach((r, i) => {
    const row = el(`<div class="rep-item"><div><div class="song">${esc(r.title)}</div><div class="artist">${esc(r.artist || "")}</div></div>
      <div style="display:flex;align-items:center;gap:8px"><span class="key-badge">${esc(r.key)}</span><button class="rep-del" data-del="1">✕</button></div></div>`);
    row.querySelector("[data-del]").onclick = () => { state.me.repertoire.splice(i, 1); save(); paintMyRep(); };
    box.appendChild(row);
  });
}

// ======================================================================
// Cassetta degli Attrezzi: Metronomo + Accordatore
// ======================================================================
function renderTools(app) {
  app.appendChild(el(`
    <div>
      <h1 class="view-title">Cassetta degli attrezzi 🧰</h1>
      <p class="view-sub">Metronomo e accordatore integrati: tutto sul leggio.</p>
      <div class="segmented">
        <button id="tMetro" class="on">⏱️ Metronomo</button>
        <button id="tTuner">🎚️ Accordatore</button>
      </div>
      <div id="toolBody"></div>
    </div>`));
  $("#tMetro").onclick = () => { $("#tMetro").classList.add("on"); $("#tTuner").classList.remove("on"); stopTuner(); renderMetronome($("#toolBody")); };
  $("#tTuner").onclick = () => { $("#tTuner").classList.add("on"); $("#tMetro").classList.remove("on"); stopMetronome(); renderTuner($("#toolBody")); };
  renderMetronome($("#toolBody"));
}

// ----- Metronomo (Web Audio) -----
const metro = { ctx: null, playing: false, bpm: 100, beats: 4, current: 0, nextTime: 0, timer: null, taps: [] };
function renderMetronome(box) {
  box.innerHTML = "";
  box.appendChild(el(`
    <div class="tool-card">
      <div class="bpm-display"><span id="bpmVal">${metro.bpm}</span><br><small>BPM</small></div>
      <div class="beat-dots" id="beatDots"></div>
      <input type="range" id="bpmRange" min="40" max="240" value="${metro.bpm}">
      <div class="bpm-controls">
        <button id="bpmMinus">−</button>
        <button class="btn" id="metroToggle">${metro.playing ? "⏸ Stop" : "▶ Avvia"}</button>
        <button id="bpmPlus">+</button>
      </div>
      <div class="row-between" style="margin-top:6px">
        <button class="btn secondary small" id="tapTempo">👆 Tap tempo</button>
        <select id="beatsSel" style="width:auto">
          ${[2, 3, 4, 5, 6].map(b => `<option value="${b}"${b === metro.beats ? " selected" : ""}>${b}/4</option>`).join("")}
        </select>
      </div>
    </div>`));
  drawBeatDots();
  const setBpm = (v) => { metro.bpm = Math.max(40, Math.min(240, v)); $("#bpmVal").textContent = metro.bpm; $("#bpmRange").value = metro.bpm; };
  $("#bpmRange").oninput = e => setBpm(+e.target.value);
  $("#bpmMinus").onclick = () => setBpm(metro.bpm - 1);
  $("#bpmPlus").onclick = () => setBpm(metro.bpm + 1);
  $("#beatsSel").onchange = e => { metro.beats = +e.target.value; metro.current = 0; drawBeatDots(); };
  $("#metroToggle").onclick = toggleMetronome;
  $("#tapTempo").onclick = tapTempo;
}
function drawBeatDots() {
  const d = $("#beatDots"); if (!d) return;
  d.innerHTML = ""; for (let i = 0; i < metro.beats; i++) d.appendChild(el(`<i class="${i === 0 ? "accent" : ""}"></i>`));
}
function ensureCtx() { if (!metro.ctx) metro.ctx = new (window.AudioContext || window.webkitAudioContext)(); if (metro.ctx.state === "suspended") metro.ctx.resume(); return metro.ctx; }
function toggleMetronome() {
  if (metro.playing) return stopMetronome(true);
  ensureCtx(); metro.playing = true; metro.current = 0; metro.nextTime = metro.ctx.currentTime + 0.05;
  metro.timer = setInterval(metroScheduler, 25);
  const b = $("#metroToggle"); if (b) b.textContent = "⏸ Stop";
}
function stopMetronome(updateBtn) {
  metro.playing = false; if (metro.timer) clearInterval(metro.timer); metro.timer = null;
  document.querySelectorAll("#beatDots i").forEach(i => i.classList.remove("on"));
  if (updateBtn) { const b = $("#metroToggle"); if (b) b.textContent = "▶ Avvia"; }
}
function metroScheduler() {
  if (!metro.playing) return;
  while (metro.nextTime < metro.ctx.currentTime + 0.12) {
    clickAt(metro.nextTime, metro.current === 0);
    const beat = metro.current, when = metro.nextTime;
    setTimeout(() => flashBeat(beat), Math.max(0, (when - metro.ctx.currentTime) * 1000));
    metro.nextTime += 60 / metro.bpm;
    metro.current = (metro.current + 1) % metro.beats;
  }
}
function clickAt(time, accent) {
  const o = metro.ctx.createOscillator(), g = metro.ctx.createGain();
  o.frequency.value = accent ? 1500 : 900;
  g.gain.setValueAtTime(0.001, time);
  g.gain.exponentialRampToValueAtTime(accent ? 0.7 : 0.4, time + 0.001);
  g.gain.exponentialRampToValueAtTime(0.001, time + 0.05);
  o.connect(g).connect(metro.ctx.destination); o.start(time); o.stop(time + 0.06);
}
function flashBeat(beat) {
  const dots = document.querySelectorAll("#beatDots i"); if (!dots.length) return;
  dots.forEach(d => d.classList.remove("on")); if (dots[beat]) dots[beat].classList.add("on");
}
function tapTempo() {
  const now = performance.now(); metro.taps.push(now); metro.taps = metro.taps.filter(t => now - t < 2500);
  if (metro.taps.length >= 2) {
    let sum = 0; for (let i = 1; i < metro.taps.length; i++) sum += metro.taps[i] - metro.taps[i - 1];
    const bpm = Math.round(60000 / (sum / (metro.taps.length - 1)));
    metro.bpm = Math.max(40, Math.min(240, bpm)); $("#bpmVal").textContent = metro.bpm; $("#bpmRange").value = metro.bpm;
  }
}

// ----- Accordatore (microfono + toni di riferimento) -----
const tuner = { ctx: null, analyser: null, stream: null, raf: null, osc: null };
const NOTE_IT = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"];
const GUITAR = [["Mi", 82.41], ["La", 110.0], ["Re", 146.83], ["Sol", 196.0], ["Si", 246.94], ["Mi", 329.63]];
function renderTuner(box) {
  box.innerHTML = "";
  box.appendChild(el(`
    <div class="tool-card">
      <div class="tuner-note" id="tNote">—</div>
      <div class="tuner-cents" id="tFreq">Avvia per accordare</div>
      <div class="tuner-meter" id="tMeter"><div class="center"></div><div class="needle" id="tNeedle"></div></div>
      <button class="btn" id="tStart" style="margin-top:14px">🎤 Avvia accordatore</button>
      <p class="view-sub" id="tHint" style="margin-top:10px">Useremo il microfono solo per rilevare la nota. Niente registrazioni.</p>
    </div>
    <div class="tool-card">
      <div class="section-label" style="margin-top:0">Toni di riferimento (chitarra)</div>
      <p class="view-sub">Tocca una corda per sentire la nota giusta.</p>
      <div class="ref-tones" id="refTones">
        ${GUITAR.map((g, i) => `<button data-freq="${g[1]}" data-i="${i}">${g[0]}<br><small style="font-weight:600;color:var(--muted)">${i === 0 ? "6ª" : i === 5 ? "1ª" : ""}</small></button>`).join("")}
      </div>
    </div>`));
  $("#tStart").onclick = startTuner;
  $("#refTones").querySelectorAll("button").forEach(b => b.onclick = () => playRef(+b.dataset.freq, b));
}
async function startTuner() {
  const btn = $("#tStart");
  try {
    tuner.ctx = tuner.ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (tuner.ctx.state === "suspended") await tuner.ctx.resume();
    if (!tuner.stream) tuner.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    const src = tuner.ctx.createMediaStreamSource(tuner.stream);
    tuner.analyser = tuner.ctx.createAnalyser(); tuner.analyser.fftSize = 2048;
    src.connect(tuner.analyser);
    if (btn) { btn.textContent = "⏹ Ferma"; btn.onclick = () => { stopTuner(); renderTuner($("#toolBody")); }; }
    $("#tHint").textContent = "Suona una nota vicino al microfono…";
    detectPitch();
  } catch (e) {
    $("#tHint").textContent = "⚠️ Microfono non disponibile o permesso negato. Usa i toni di riferimento qui sotto per accordarti a orecchio.";
  }
}
function stopTuner() {
  if (tuner.raf) cancelAnimationFrame(tuner.raf); tuner.raf = null;
  if (tuner.stream) { tuner.stream.getTracks().forEach(t => t.stop()); tuner.stream = null; }
  if (tuner.osc) { try { tuner.osc.stop(); } catch (e) {} tuner.osc = null; }
}
function detectPitch() {
  const buf = new Float32Array(tuner.analyser.fftSize);
  const loop = () => {
    tuner.analyser.getFloatTimeDomainData(buf);
    const freq = autoCorrelate(buf, tuner.ctx.sampleRate);
    const noteEl = $("#tNote"), freqEl = $("#tFreq"), meter = $("#tMeter"), needle = $("#tNeedle");
    if (noteEl && freq > 0) {
      const midi = Math.round(12 * Math.log2(freq / 440) + 69);
      const ref = 440 * Math.pow(2, (midi - 69) / 12);
      const cents = Math.round(1200 * Math.log2(freq / ref));
      noteEl.textContent = NOTE_IT[((midi % 12) + 12) % 12];
      freqEl.textContent = `${freq.toFixed(1)} Hz · ${cents > 0 ? "+" : ""}${cents} cent`;
      needle.style.left = `${50 + Math.max(-50, Math.min(50, cents))}%`;
      meter.classList.toggle("in", Math.abs(cents) <= 5);
    } else if (freqEl) { freqEl.textContent = "…"; }
    tuner.raf = requestAnimationFrame(loop);
  };
  loop();
}
function autoCorrelate(buf, sampleRate) {
  let SIZE = buf.length, rms = 0;
  for (let i = 0; i < SIZE; i++) rms += buf[i] * buf[i];
  rms = Math.sqrt(rms / SIZE);
  if (rms < 0.01) return -1; // troppo silenzio
  let r1 = 0, r2 = SIZE - 1, thres = 0.2;
  for (let i = 0; i < SIZE / 2; i++) if (Math.abs(buf[i]) < thres) { r1 = i; break; }
  for (let i = 1; i < SIZE / 2; i++) if (Math.abs(buf[SIZE - i]) < thres) { r2 = SIZE - i; break; }
  buf = buf.slice(r1, r2); SIZE = buf.length;
  const c = new Array(SIZE).fill(0);
  for (let i = 0; i < SIZE; i++) for (let j = 0; j < SIZE - i; j++) c[i] += buf[j] * buf[j + i];
  let d = 0; while (c[d] > c[d + 1]) d++;
  let maxval = -1, maxpos = -1;
  for (let i = d; i < SIZE; i++) if (c[i] > maxval) { maxval = c[i]; maxpos = i; }
  let T0 = maxpos;
  const x1 = c[T0 - 1] || 0, x2 = c[T0] || 0, x3 = c[T0 + 1] || 0;
  const a = (x1 + x3 - 2 * x2) / 2, b = (x3 - x1) / 2;
  if (a) T0 = T0 - b / (2 * a);
  return T0 > 0 ? sampleRate / T0 : -1;
}
function playRef(freq, btn) {
  ensureTunerCtx();
  if (tuner.osc) { try { tuner.osc.stop(); } catch (e) {} tuner.osc = null; document.querySelectorAll("#refTones button").forEach(b => b.classList.remove("on")); if (btn.dataset.playing) { btn.dataset.playing = ""; return; } }
  document.querySelectorAll("#refTones button").forEach(b => { b.classList.remove("on"); b.dataset.playing = ""; });
  const o = tuner.ctx.createOscillator(), g = tuner.ctx.createGain();
  o.type = "sine"; o.frequency.value = freq;
  g.gain.setValueAtTime(0.0001, tuner.ctx.currentTime);
  g.gain.exponentialRampToValueAtTime(0.25, tuner.ctx.currentTime + 0.02);
  o.connect(g).connect(tuner.ctx.destination); o.start();
  tuner.osc = o; btn.classList.add("on"); btn.dataset.playing = "1";
  setTimeout(() => { if (tuner.osc === o) { try { o.stop(); } catch (e) {} tuner.osc = null; btn.classList.remove("on"); btn.dataset.playing = ""; } }, 2000);
}
function ensureTunerCtx() { tuner.ctx = tuner.ctx || new (window.AudioContext || window.webkitAudioContext)(); if (tuner.ctx.state === "suspended") tuner.ctx.resume(); }

// ---------- Modal helpers ----------
function openModal(innerHTML) {
  const root = $("#modalRoot"); root.innerHTML = "";
  const back = el(`<div class="modal-backdrop"><div class="modal"><div class="grip"></div>${innerHTML}</div></div>`);
  back.onclick = e => { if (e.target === back) closeModal(); };
  root.appendChild(back);
}
function closeModal() { $("#modalRoot").innerHTML = ""; }

// ---------- City switch ----------
$("#cityBtn").onclick = () => {
  const c = prompt("In quale città vuoi cercare?", state.me.city);
  if (c) { state.me.city = c.trim(); $("#cityLabel").textContent = state.me.city; save(); }
};

// ---------- Init ----------
document.querySelectorAll(".tab").forEach(t => t.onclick = () => navigate(t.dataset.view));
$("#cityLabel").textContent = state.me.city;
navigate("discover");

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}
