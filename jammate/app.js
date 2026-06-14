/* JamMate — logica dell'app (prototipo MVP).
 * Single-page app in JavaScript puro, senza framework e senza build step:
 * basta aprire index.html. I dati persistono nel browser (localStorage). */

// ---------- Stato & persistenza ----------
const STORE_KEY = "jammate_state_v1";

function loadState() {
  const raw = localStorage.getItem(STORE_KEY);
  if (raw) {
    try { return JSON.parse(raw); } catch (e) { /* fallthrough */ }
  }
  return {
    profiles: SEED_PROFILES,
    events: SEED_EVENTS,
    messages: SEED_MESSAGES,
    me: {
      id: "me", name: "", avatar: "🎵", city: "Milano", distanceKm: 0,
      instruments: [], level: "Intermedio", genres: [], bio: "",
      links: { youtube: "", spotify: "", instagram: "" },
      repertoire: [], endo: { puntualita: 0, tecnica: 0, attitudine: 0 }
    },
    filters: { instrument: "", level: "", genre: "", distance: 30 },
    onboarded: false
  };
}

let state = loadState();
function save() { localStorage.setItem(STORE_KEY, JSON.stringify(state)); }

// ---------- Utility ----------
const $ = (sel, root = document) => root.querySelector(sel);
const el = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(msg) {
  const t = el(`<div class="toast">${esc(msg)}</div>`);
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2200);
}

function options(list, selected, placeholder) {
  let o = placeholder ? `<option value="">${esc(placeholder)}</option>` : "";
  o += list.map(v => `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(v)}</option>`).join("");
  return o;
}

function chips(list, selected) {
  return list.map(v => `<span class="chip${selected.includes(v) ? " on" : ""}" data-chip="${esc(v)}">${esc(v)}</span>`).join("");
}

function endoBlock(endo) {
  const rows = [["Puntualità", endo.puntualita], ["Tecnica", endo.tecnica], ["Attitudine", endo.attitudine]];
  return `<div class="endo">${rows.map(([l, n]) => `
    <span class="lbl">${l}</span>
    <span class="num">${n}%</span>
    <div class="bar" style="grid-column:1/-1"><i style="width:${n}%"></i></div>`).join("")}</div>`;
}

function avgScore(endo) {
  return Math.round((endo.puntualita + endo.tecnica + endo.attitudine) / 3);
}

// ---------- Router ----------
let currentView = "discover";
function navigate(view) {
  currentView = view;
  if (view === "create") { openCreateSheet(); return; }
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.view === view));
  render();
}

function render() {
  const app = $("#app");
  app.innerHTML = "";
  if (!state.onboarded) { renderOnboarding(app); return; }
  ({ discover: renderDiscover, board: renderBoard, messages: renderMessages, profile: renderProfile }[currentView] || renderDiscover)(app);
}

// ---------- Onboarding ----------
function renderOnboarding(app) {
  app.appendChild(el(`
    <div>
      <h1 class="view-title">Benvenuto su JamMate 🎶</h1>
      <p class="view-sub">Trova musicisti vicino a te e suona insieme dal vivo. Crea il tuo profilo in 30 secondi.</p>
      <div class="card" style="cursor:default">
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
    if (!name) { toast("Inserisci almeno il nome"); return; }
    state.me.name = name;
    state.me.city = $("#obCity").value.trim() || "Milano";
    state.me.avatar = ["🎸","🎤","🥁","🎹","🎻","🎷"][Math.floor(Math.random()*6)];
    state.me.instruments = selIns;
    state.me.level = $("#obLevel").value;
    state.me.genres = selGen;
    state.onboarded = true;
    save();
    toast("Profilo creato! Ora aggiungi il tuo repertorio 🎵");
    navigate("discover");
  };
}

function toggleChip(node, arr) {
  const v = node.dataset.chip;
  const i = arr.indexOf(v);
  if (i >= 0) arr.splice(i, 1); else arr.push(v);
  node.classList.toggle("on");
}

// ---------- Vista: Scopri (Discovery + filtri) ----------
function renderDiscover(app) {
  const f = state.filters;
  app.appendChild(el(`
    <div>
      <h1 class="view-title">Scopri musicisti</h1>
      <p class="view-sub">Filtra per trovare esattamente chi cerchi vicino a te.</p>
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
      <div id="results"></div>
    </div>`));

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
    (p.distanceKm <= f.distance)
  ).sort((a, b) => a.distanceKm - b.distanceKm);
}

function paintResults() {
  const box = $("#results");
  if (!box) return;
  const list = matchProfiles();
  if (!list.length) { box.innerHTML = `<div class="empty">Nessun musicista trovato con questi filtri.<br>Prova ad allargare la distanza o togliere qualche filtro.</div>`; return; }
  box.innerHTML = `<p class="view-sub">${list.length} musicist${list.length === 1 ? "a" : "i"} trovat${list.length === 1 ? "o" : "i"}</p>`;
  list.forEach(p => box.appendChild(profileCard(p)));
}

function profileCard(p) {
  const c = el(`
    <div class="card">
      <div class="card-head">
        <div class="avatar">${p.avatar}</div>
        <div class="meta">
          <div class="name">${esc(p.name)} <span class="score">★ ${avgScore(p.endo)}</span></div>
          <div class="loc">📍 ${esc(p.city)} · ${p.distanceKm} km · ${esc(p.level)}</div>
        </div>
      </div>
      <div class="tags">
        ${p.instruments.map(i => `<span class="tag accent">${esc(i)}</span>`).join("")}
        ${p.genres.slice(0,3).map(g => `<span class="tag">${esc(g)}</span>`).join("")}
      </div>
      <div class="tags" style="margin-top:6px"><span class="dist">🎵 ${p.repertoire.length} brani nel repertorio</span></div>
    </div>`);
  c.onclick = () => openProfileSheet(p);
  return c;
}

// ---------- Sheet: dettaglio profilo ----------
function openProfileSheet(p) {
  const links = Object.entries(p.links).filter(([, v]) => v);
  openModal(`
    <div style="text-align:center">
      <div class="avatar lg" style="margin:0 auto">${p.avatar}</div>
      <h2>${esc(p.name)}</h2>
      <div class="loc">📍 ${esc(p.city)} · ${p.distanceKm} km · ${esc(p.level)} · <span class="score">★ ${avgScore(p.endo)}</span></div>
    </div>
    <div class="tags" style="justify-content:center;margin-top:10px">
      ${p.instruments.map(i => `<span class="tag accent">${esc(i)}</span>`).join("")}
      ${p.genres.map(g => `<span class="tag">${esc(g)}</span>`).join("")}
    </div>
    ${p.bio ? `<div class="section-label">Bio</div><p style="margin:0;color:var(--text);line-height:1.5">${esc(p.bio)}</p>` : ""}
    ${links.length ? `<div class="section-label">Ascolta</div><div class="linkrow">${links.map(([k, v]) => `<a href="${esc(v)}" target="_blank" rel="noopener">${({youtube:"▶ YouTube",spotify:"♫ Spotify",instagram:"◎ Instagram"})[k] || k}</a>`).join("")}</div>` : ""}
    <div class="section-label">Repertorio & tonalità</div>
    ${p.repertoire.length ? p.repertoire.map(r => `
      <div class="rep-item">
        <div><div class="song">${esc(r.title)}</div><div class="artist">${esc(r.artist || "")}</div></div>
        <span class="key-badge">${esc(r.key)}</span>
      </div>`).join("") : `<p class="view-sub">Nessun brano indicato.</p>`}
    <div class="section-label">Reputazione</div>
    ${endoBlock(p.endo)}
    <div style="margin-top:22px"><button class="btn" id="contactBtn">💬 Contatta ${esc(p.name.split(" ")[0])}</button></div>
  `);
  $("#contactBtn").onclick = () => { closeModal(); navigate("messages"); setTimeout(() => openChat(p), 50); };
}

// ---------- Vista: Bacheca eventi/annunci ----------
function renderBoard(app) {
  app.appendChild(el(`
    <div>
      <h1 class="view-title">Bacheca annunci</h1>
      <p class="view-sub">Band in cerca di membri e jam session vicino a te. Candidati agli slot liberi.</p>
      <div id="eventList"></div>
    </div>`));
  const box = $("#eventList");
  if (!state.events.length) { box.innerHTML = `<div class="empty">Ancora nessun annuncio. Creane uno con il pulsante ＋</div>`; return; }
  state.events.forEach(ev => box.appendChild(eventCard(ev)));
}

function eventCard(ev) {
  const open = ev.slots.filter(s => !s.filled).length;
  const c = el(`
    <div class="card">
      <div class="row-between">
        <span class="event-date">📅 ${formatDate(ev.date)}</span>
        ${open ? `<span class="badge-new">${open} slot liber${open===1?"o":"i"}</span>` : ""}
      </div>
      <div style="font-weight:700;font-size:1.08rem;margin:6px 0 2px">${esc(ev.title)}</div>
      <div class="loc">${ev.authorAvatar} ${esc(ev.author)} · 📍 ${esc(ev.city)} · ${ev.distanceKm} km</div>
      <div class="tags" style="margin-top:8px">${ev.genres.map(g => `<span class="tag">${esc(g)}</span>`).join("")}</div>
      <div class="slot-row">
        ${ev.slots.map((s, i) => `<span class="slot ${s.filled ? "filled" : "open"}" data-slot="${i}">${s.filled ? "✓" : "+"} ${esc(s.instrument)}</span>`).join("")}
      </div>
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
    <div class="section-label">Descrizione</div>
    <p style="margin:0;line-height:1.5">${esc(ev.description)}</p>
    <div class="section-label">Slot strumenti</div>
    <div id="slotList"></div>
  `);
  const sl = $("#slotList");
  ev.slots.forEach((s, i) => {
    const row = el(`<div class="rep-item">
      <span class="song">${s.filled ? "✓" : "🔎"} ${esc(s.instrument)}</span>
      ${s.filled ? `<span class="tag lvl">Occupato</span>` : `<button class="btn small" data-apply="${i}">Candidati</button>`}
    </div>`);
    const btn = row.querySelector("[data-apply]");
    if (btn) btn.onclick = () => {
      s.filled = true; s.applicant = state.me.name; save();
      toast(`Candidatura inviata per: ${s.instrument} 🎉`);
      closeModal(); renderBoard($("#app"));
    };
    sl.appendChild(row);
  });
}

// ---------- Vista: Chat ----------
function renderMessages(app) {
  app.appendChild(el(`
    <div>
      <h1 class="view-title">Messaggi</h1>
      <p class="view-sub">Accordati senza scambiare il numero di telefono.</p>
      <div id="threads"></div>
    </div>`));
  const box = $("#threads");
  const ids = Object.keys(state.messages);
  if (!ids.length) { box.innerHTML = `<div class="empty">Nessuna conversazione.<br>Apri un profilo da "Scopri" e premi <b>Contatta</b>.</div>`; return; }
  ids.forEach(id => {
    const p = state.profiles.find(x => x.id === id);
    if (!p) return;
    const last = state.messages[id][state.messages[id].length - 1];
    const c = el(`<div class="card">
      <div class="card-head">
        <div class="avatar">${p.avatar}</div>
        <div class="meta"><div class="name">${esc(p.name)}</div>
        <div class="loc">${esc(last.from === "me" ? "Tu: " : "")}${esc(last.text)}</div></div>
      </div></div>`);
    c.onclick = () => openChat(p);
    box.appendChild(c);
  });
}

function openChat(p) {
  if (!state.messages[p.id]) state.messages[p.id] = [];
  openModal(`
    <div class="card-head" style="margin-bottom:12px">
      <div class="avatar">${p.avatar}</div>
      <div class="meta"><div class="name">${esc(p.name)}</div><div class="loc">📍 ${esc(p.city)} · ${p.distanceKm} km</div></div>
    </div>
    <div class="msg-thread" id="thread"></div>
    <div class="composer">
      <input type="text" id="msgInput" placeholder="Scrivi un messaggio…" />
      <button class="btn small" id="sendMsg">Invia</button>
    </div>
  `);
  paintThread(p);
  const send = () => {
    const v = $("#msgInput").value.trim();
    if (!v) return;
    state.messages[p.id].push({ from: "me", text: v });
    save(); $("#msgInput").value = ""; paintThread(p);
    // risposta automatica simulata (solo prototipo)
    setTimeout(() => {
      state.messages[p.id].push({ from: "them", text: "Perfetto! Ci sentiamo per organizzare una prova 🤘" });
      save(); paintThread(p);
    }, 900);
  };
  $("#sendMsg").onclick = send;
  $("#msgInput").addEventListener("keydown", e => { if (e.key === "Enter") send(); });
}

function paintThread(p) {
  const t = $("#thread");
  if (!t) return;
  t.innerHTML = state.messages[p.id].map(m => `<div class="bubble ${m.from}">${esc(m.text)}</div>`).join("");
  t.scrollTop = t.scrollHeight;
}

// ---------- Vista: Profilo (il mio) ----------
function renderProfile(app) {
  const m = state.me;
  app.appendChild(el(`
    <div>
      <div style="text-align:center;margin-bottom:8px">
        <div class="avatar lg" style="margin:0 auto">${m.avatar}</div>
        <h1 class="view-title" style="margin-bottom:0">${esc(m.name || "Il mio profilo")}</h1>
        <div class="loc">📍 ${esc(m.city)} · ${esc(m.level)}</div>
      </div>
      <div class="hint">💡 Il tuo <b>repertorio con le tonalità</b> è ciò che ti rende trovabile. È la marcia in più di JamMate: indica i brani che sai suonare e in che tonalità li esegui.</div>

      <div class="section-label">Repertorio & tonalità</div>
      <div id="myRep"></div>
      <div class="card" style="cursor:default">
        <div class="add-rep">
          <div><label class="field">Brano</label><input type="text" id="repTitle" placeholder="Es. Wonderwall"></div>
          <div><label class="field">Artista</label><input type="text" id="repArtist" placeholder="Es. Oasis"></div>
          <div><label class="field">Tonalità</label><select id="repKey">${options(KEYS, "Do")}</select></div>
          <button class="btn small" id="addRep">Aggiungi</button>
        </div>
      </div>

      <div class="section-label">Strumenti</div>
      <div class="chips" id="myIns">${chips(INSTRUMENTS, m.instruments)}</div>
      <div class="section-label">Generi</div>
      <div class="chips" id="myGen">${chips(GENRES, m.genres)}</div>

      <div class="section-label">Bio</div>
      <textarea id="myBio" placeholder="Racconta chi sei e cosa cerchi…">${esc(m.bio)}</textarea>

      <div class="section-label">Link (per farti ascoltare)</div>
      <input type="text" id="lkYt" placeholder="Link YouTube" value="${esc(m.links.youtube)}" style="margin-bottom:8px">
      <input type="text" id="lkSp" placeholder="Link Spotify" value="${esc(m.links.spotify)}" style="margin-bottom:8px">
      <input type="text" id="lkIg" placeholder="Link Instagram" value="${esc(m.links.instagram)}">

      <button class="btn" id="saveProfile" style="margin-top:20px">Salva profilo</button>
      <button class="btn secondary" id="resetApp" style="margin-top:10px">Azzera dati demo</button>
    </div>`));

  paintMyRep();
  $("#addRep").onclick = () => {
    const title = $("#repTitle").value.trim();
    if (!title) { toast("Scrivi il titolo del brano"); return; }
    m.repertoire.push({ title, artist: $("#repArtist").value.trim(), key: $("#repKey").value });
    save(); $("#repTitle").value = ""; $("#repArtist").value = ""; paintMyRep();
    toast("Brano aggiunto al repertorio 🎵");
  };
  app.querySelectorAll("#myIns .chip").forEach(c => c.onclick = () => toggleChip(c, m.instruments));
  app.querySelectorAll("#myGen .chip").forEach(c => c.onclick = () => toggleChip(c, m.genres));
  $("#saveProfile").onclick = () => {
    m.bio = $("#myBio").value.trim();
    m.links = { youtube: $("#lkYt").value.trim(), spotify: $("#lkSp").value.trim(), instagram: $("#lkIg").value.trim() };
    save(); toast("Profilo salvato ✓");
  };
  $("#resetApp").onclick = () => {
    if (confirm("Azzerare tutti i dati e ripartire dalla demo?")) { localStorage.removeItem(STORE_KEY); state = loadState(); navigate("discover"); }
  };
}

function paintMyRep() {
  const box = $("#myRep");
  if (!box) return;
  if (!state.me.repertoire.length) { box.innerHTML = `<p class="view-sub">Nessun brano ancora. Aggiungine qui sotto 👇</p>`; return; }
  box.innerHTML = "";
  state.me.repertoire.forEach((r, i) => {
    const row = el(`<div class="rep-item">
      <div><div class="song">${esc(r.title)}</div><div class="artist">${esc(r.artist || "")}</div></div>
      <div style="display:flex;align-items:center;gap:8px"><span class="key-badge">${esc(r.key)}</span><button class="rep-del" data-del="${i}">✕</button></div>
    </div>`);
    row.querySelector("[data-del]").onclick = () => { state.me.repertoire.splice(i, 1); save(); paintMyRep(); };
    box.appendChild(row);
  });
}

// ---------- Sheet: crea annuncio ----------
function openCreateSheet() {
  openModal(`
    <h2>Nuovo annuncio 📌</h2>
    <p class="view-sub">Cerchi membri per una band o vuoi organizzare una jam? Pubblica qui.</p>
    <label class="field">Titolo</label>
    <input type="text" id="evTitle" placeholder="Es. Cerchiamo bassista rock">
    <label class="field" style="margin-top:10px">Nome band / organizzatore</label>
    <input type="text" id="evAuthor" placeholder="Es. The Riffs" value="${esc(state.me.name)}">
    <div class="filter-row" style="margin-top:10px">
      <div><label class="field">Città</label><input type="text" id="evCity" value="${esc(state.me.city)}"></div>
      <div><label class="field">Data</label><input type="date" id="evDate"></div>
    </div>
    <label class="field" style="margin-top:10px">Generi</label>
    <div class="chips" id="evGenres">${chips(GENRES, [])}</div>
    <label class="field" style="margin-top:10px">Strumenti cercati (slot liberi)</label>
    <div class="chips" id="evSlots">${chips(INSTRUMENTS, [])}</div>
    <label class="field" style="margin-top:10px">Descrizione</label>
    <textarea id="evDesc" placeholder="Dettagli, sala prove, orari…"></textarea>
    <button class="btn" id="evCreate" style="margin-top:18px">Pubblica annuncio</button>
  `);
  const selGen = [], selSlots = [];
  document.querySelectorAll("#evGenres .chip").forEach(c => c.onclick = () => toggleChip(c, selGen));
  document.querySelectorAll("#evSlots .chip").forEach(c => c.onclick = () => toggleChip(c, selSlots));
  $("#evCreate").onclick = () => {
    const title = $("#evTitle").value.trim();
    if (!title) { toast("Inserisci un titolo"); return; }
    if (!selSlots.length) { toast("Seleziona almeno uno strumento cercato"); return; }
    state.events.unshift({
      id: "e" + Date.now(), title,
      author: $("#evAuthor").value.trim() || state.me.name || "Anonimo",
      authorAvatar: state.me.avatar, city: $("#evCity").value.trim() || "Milano", distanceKm: 0,
      date: $("#evDate").value || new Date().toISOString().slice(0, 10),
      genres: selGen, description: $("#evDesc").value.trim(),
      slots: selSlots.map(i => ({ instrument: i, filled: false }))
    });
    save(); closeModal(); toast("Annuncio pubblicato! 📢"); navigate("board");
  };
}

// ---------- Modal helpers ----------
function openModal(innerHTML) {
  const root = $("#modalRoot");
  root.innerHTML = "";
  const back = el(`<div class="modal-backdrop"><div class="modal"><div class="grip"></div>${innerHTML}</div></div>`);
  back.onclick = e => { if (e.target === back) closeModal(); };
  root.appendChild(back);
}
function closeModal() { $("#modalRoot").innerHTML = ""; }

// ---------- Helpers vari ----------
function formatDate(iso) {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("it-IT", { weekday: "short", day: "numeric", month: "long" });
  } catch (e) { return iso; }
}

// ---------- City switch ----------
$("#cityBtn").onclick = () => {
  const c = prompt("In quale città vuoi cercare?", state.me.city);
  if (c) { state.me.city = c.trim(); $("#cityLabel").textContent = state.me.city; save(); }
};

// ---------- Init ----------
document.querySelectorAll(".tab").forEach(t => t.onclick = () => navigate(t.dataset.view));
$("#cityLabel").textContent = state.me.city;
navigate("discover");

// ---------- PWA service worker ----------
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}
