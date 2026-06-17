/* JamMate — modulo "social & community" (prototipo, dati locali).
 * Contiene: Feed sociale (#11), Notifiche (#10), Mappa jam geolocalizzate (#9),
 * Lezioni con calendario + pagamento (#12).
 * Usa gli helper globali definiti in app.js/gigs.js ($,el,esc,openModal,closeModal,
 * toast,avatarTag,save,state,navigate,formatDate,options,chips,toggleChip,currentView,
 * renderBoard2,rerenderPalco) e i dati/costanti di data.js (LEVELS,GENRES,INSTRUMENTS,
 * GRADS,SEED_PROFILES,levelsOf,levelRank).
 * Reso modulare apposta: al deploy del backend, ogni sezione aggancia le sue API. */

// ------------------------------------------------------------- Helper comuni
function timeAgo(ts) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return "ora";
  const m = Math.floor(s / 60); if (m < 60) return m + " min fa";
  const h = Math.floor(m / 60); if (h < 24) return h + " h fa";
  const d = Math.floor(h / 24); if (d < 7) return d + " g fa";
  try { return new Date(ts).toLocaleDateString("it-IT", { day: "numeric", month: "short" }); } catch (e) { return ""; }
}
// Selettore immagine generico → dataURL. Le GIF vengono mantenute così come sono
// (per preservare l'animazione); le altre immagini sono ridimensionate in JPEG.
function pickImage(cb, maxDim) {
  maxDim = maxDim || 1000;
  const inp = el(`<input type="file" accept="image/*,image/gif" style="display:none">`);
  document.body.appendChild(inp);
  inp.onchange = () => {
    const f = inp.files && inp.files[0]; if (!f) { inp.remove(); return; }
    const rd = new FileReader();
    rd.onload = () => {
      if (f.type === "image/gif") { // GIF: niente canvas, mantieni l'animazione
        if (rd.result.length > 6000000) { toast("GIF troppo pesante (max ~4MB)"); inp.remove(); return; }
        cb(rd.result); inp.remove(); return;
      }
      const img = new Image();
      img.onload = () => {
        const r = Math.min(1, maxDim / Math.max(img.width, img.height));
        const w = Math.round(img.width * r), h = Math.round(img.height * r);
        const c = document.createElement("canvas"); c.width = w; c.height = h;
        c.getContext("2d").drawImage(img, 0, 0, w, h);
        try { cb(c.toDataURL("image/jpeg", 0.8)); } catch (e) { toast("Immagine non valida"); }
        inp.remove();
      };
      img.onerror = () => { toast("Immagine non valida"); inp.remove(); };
      img.src = rd.result;
    };
    rd.readAsDataURL(f);
  };
  inp.click();
}
// Inserisce testo (emoji) nella textarea alla posizione del cursore.
function insertAtCursor(ta, text) {
  if (!ta) return;
  const s = ta.selectionStart != null ? ta.selectionStart : ta.value.length;
  const e = ta.selectionEnd != null ? ta.selectionEnd : ta.value.length;
  ta.value = ta.value.slice(0, s) + text + ta.value.slice(e);
  ta.focus(); const pos = s + text.length; try { ta.setSelectionRange(pos, pos); } catch (er) {}
}
// Reazioni: normalizza il vecchio formato (likes/likedByMe) e calcola il riepilogo.
function normReactions(p) {
  if (!p.reactions) { p.reactions = {}; if (p.likes) p.reactions["👍"] = p.likes; p.myReaction = p.likedByMe ? "👍" : (p.myReaction || null); }
  if (p.myReaction === undefined) p.myReaction = null;
  return p;
}
function reactionSummary(p) {
  normReactions(p);
  const counts = Object.assign({}, p.reactions);
  if (p.myReaction) counts[p.myReaction] = (counts[p.myReaction] || 0) + 1;
  const emojis = Object.keys(counts).filter(e => counts[e] > 0).sort((a, b) => counts[b] - counts[a]);
  return { emojis: emojis.slice(0, 3), total: emojis.reduce((s, e) => s + counts[e], 0) };
}
function setReaction(p, emoji) { normReactions(p); p.myReaction = p.myReaction === emoji ? null : emoji; save(); }

// ------------------------------------------------------------- Notifiche (#10)
function notify(icon, text, opts) {
  state.notifications = state.notifications || [];
  state.notifications.unshift({ id: "n" + Date.now() + Math.random().toString(36).slice(2, 6), icon, text, ts: Date.now(), read: false, view: opts && opts.view });
  if (state.notifications.length > 50) state.notifications.length = 50;
  save(); if (typeof updateBell === "function") updateBell();
}
function notifRow(n) {
  return `<div class="notif-row${n.view ? " tap" : ""}${n.read ? "" : " unread"}"${n.view ? ` data-view="${esc(n.view)}"` : ""}>
    <span class="notif-icon">${n.icon || "🔔"}</span>
    <div><div>${esc(n.text)}</div><div class="notif-time">${timeAgo(n.ts)}</div></div></div>`;
}
function openNotifications() {
  const list = state.notifications || [];
  openModal(`<div class="row-between"><h2 style="margin:0">🔔 Notifiche</h2>${list.length ? `<button class="btn small secondary" id="clearNotif">Pulisci</button>` : ""}</div>
    <div id="notifList" style="margin-top:12px">${list.length ? list.map(notifRow).join("") : `<div class="empty">Nessuna notifica per ora.</div>`}</div>`);
  document.querySelectorAll("#notifList [data-view]").forEach(r => r.onclick = () => { closeModal(); navigate(r.dataset.view); });
  if ($("#clearNotif")) $("#clearNotif").onclick = () => { state.notifications = []; save(); updateBell(); closeModal(); };
  // segna tutte come lette all'apertura
  list.forEach(n => n.read = true); save(); updateBell();
}

// ------------------------------------------------------------- Feed sociale (#11)
// Reazioni disponibili (#più reazioni) ed emoji per il composer (#più icone).
const REACTIONS = ["👍", "❤️", "🔥", "😂", "🎸", "👏", "😮"];
const POST_EMOJIS = ["🎸", "🎹", "🥁", "🎤", "🎷", "🎺", "🎻", "🎶", "🎵", "🔥", "❤️", "😂", "😍", "🤘", "👏", "🙌", "✨", "🍺", "📅", "📍", "🎉", "😎", "💯", "🚀"];
const SEED_POSTS = [
  { id: "sp1", authorId: "u2", name: "Giulia Ferri", avatar: "🎤", color: GRADS[4], text: "Ieri sera prima serata con la nuova cover band 🎶 pubblico fantastico, grazie a tutti! Prossima data tra due settimane.", image: "", ts: Date.now() - 3 * 3600e3, reactions: { "🔥": 9, "❤️": 4, "👏": 3 }, myReaction: null, comments: [{ name: "Luca Greco", text: "Grandi! 🔥", ts: Date.now() - 2 * 3600e3 }] },
  { id: "sp2", authorId: "u7", name: "Tommaso Riva", avatar: "🎷", color: GRADS[5], text: "Cerco gente per una jam jazz domenica al parco. Si improvvisa, si chiacchiera, si beve qualcosa 🍺 Chi c'è?", image: "", ts: Date.now() - 9 * 3600e3, reactions: { "👍": 6, "🎸": 2 }, myReaction: null, comments: [] },
  { id: "sp3", authorId: "u1", name: "Marco Bassani", avatar: "🎸", color: GRADS[0], text: "Nuovo ampli, nuovo suono. Provato stamattina in sala, che goduria 🤘", image: "", ts: Date.now() - 28 * 3600e3, reactions: { "🔥": 14, "😮": 5, "🎸": 3 }, myReaction: null, comments: [{ name: "Davide Conti", text: "Quale hai preso?", ts: Date.now() - 26 * 3600e3 }] }
];
function feedPosts() { return [...(state.posts || []), ...SEED_POSTS]; }
function renderFeed(app) {
  app.appendChild(el(`<div>
    <h1 class="view-title">Feed 🌐</h1>
    <p class="view-sub">Cosa succede nella tua scena musicale: jam, prove, serate, traguardi.</p>
    <div class="card flat" id="composer">
      <div class="card-head">${avatarTag(state.me)}<div class="meta"><div class="name">${esc(state.me.name || "Tu")}</div></div></div>
      <textarea id="postText" placeholder="Condividi qualcosa con la community…"></textarea>
      <div class="emoji-bar" id="emojiBar" hidden>${POST_EMOJIS.map(e => `<button type="button" data-e="${e}">${e}</button>`).join("")}</div>
      <div id="postPreview"></div>
      <div class="row-between" style="margin-top:8px">
        <div style="display:flex;gap:6px">
          <button class="btn small secondary" id="postEmoji">😀</button>
          <button class="btn small secondary" id="postPhoto">🖼️ Foto / GIF</button>
        </div>
        <button class="btn small" id="postSend">Pubblica</button>
      </div>
    </div>
    <div id="feedList"></div>
  </div>`));
  let pendingImg = "";
  $("#postEmoji").onclick = () => { const b = $("#emojiBar"); b.hidden = !b.hidden; };
  $("#emojiBar").querySelectorAll("[data-e]").forEach(b => b.onclick = () => insertAtCursor($("#postText"), b.dataset.e));
  $("#postPhoto").onclick = () => pickImage(d => { pendingImg = d; $("#postPreview").innerHTML = `<img class="post-img" src="${d}" alt="anteprima">`; });
  $("#postSend").onclick = () => {
    const text = $("#postText").value.trim();
    if (!text && !pendingImg) return toast("Scrivi qualcosa o aggiungi una foto");
    const me = state.me;
    state.posts = state.posts || [];
    const post = { id: "p" + Date.now(), authorId: "me", name: me.name || "Tu", avatar: me.avatar, color: me.color, photo: me.photo || "", text, image: pendingImg, ts: Date.now(), reactions: {}, myReaction: null, comments: [] };
    state.posts.unshift(post); save();
    $("#postText").value = ""; $("#postPreview").innerHTML = ""; pendingImg = "";
    toast("Pubblicato 🎉"); renderFeedBody();
    simulateEngagement(post.id);
  };
  renderFeedBody();
}
function renderFeedBody() {
  const box = $("#feedList"); if (!box) return;
  box.innerHTML = "";
  feedPosts().forEach(p => box.appendChild(postCard(p)));
}
function postCard(p) {
  const s = reactionSummary(p);
  const canDm = p.authorId && p.authorId !== "me";
  const c = el(`<div class="card post">
    <div class="card-head">${avatarTag(p)}<div class="meta">
      <div class="name">${esc(p.name)}</div><div class="loc">${timeAgo(p.ts)}</div></div></div>
    ${p.text ? `<div class="post-text">${esc(p.text)}</div>` : ""}
    ${p.image ? `<img class="post-img" src="${p.image}" alt="contenuto del post">` : ""}
    <div class="react-picker" hidden>${REACTIONS.map(r => `<button data-r="${r}">${r}</button>`).join("")}</div>
    <div class="post-actions">
      <button class="post-act${p.myReaction ? " reacted" : ""}" data-react>${s.emojis.length ? s.emojis.join("") : "😀"} <span>${s.total}</span></button>
      <button class="post-act" data-cmt>💬 <span>${(p.comments || []).length}</span></button>
      ${canDm ? `<button class="post-act" data-dm>✉️ Scrivi</button>` : ""}
    </div>
    <div class="post-comments" hidden></div>
  </div>`);
  const picker = c.querySelector(".react-picker"), reactBtn = c.querySelector("[data-react]");
  reactBtn.onclick = () => { picker.hidden = !picker.hidden; };
  picker.querySelectorAll("[data-r]").forEach(b => b.onclick = () => {
    setReaction(p, b.dataset.r); picker.hidden = true;
    const ss = reactionSummary(p);
    reactBtn.classList.toggle("reacted", !!p.myReaction);
    reactBtn.innerHTML = `${ss.emojis.length ? ss.emojis.join("") : "😀"} <span>${ss.total}</span>`;
  });
  const cmtBox = c.querySelector(".post-comments");
  c.querySelector("[data-cmt]").onclick = () => { cmtBox.hidden = !cmtBox.hidden; if (!cmtBox.hidden) paintComments(p, cmtBox, c); };
  if (canDm) c.querySelector("[data-dm]").onclick = () => dmAuthor(p.authorId, p.name);
  return c;
}
// Messaggio privato a un autore di feed/bacheca.
function startDM(p) {
  if (!state.matches.includes(p.id)) state.matches.push(p.id);
  if (!state.messages[p.id]) state.messages[p.id] = [];
  save(); navigate("messages"); setTimeout(() => openChat(p), 50);
}
function dmAuthor(profileId, fallbackName) {
  const p = (state.profiles || []).find(x => x.id === profileId);
  if (p) return startDM(p);
  toast("Profilo non disponibile per il messaggio");
}
function paintComments(p, box, card) {
  p.comments = p.comments || [];
  box.innerHTML = p.comments.map(cm => `<div class="comment"><b>${esc(cm.name)}</b> ${esc(cm.text)} <span class="notif-time">· ${timeAgo(cm.ts)}</span></div>`).join("")
    + `<div class="add-comment"><input type="text" placeholder="Scrivi un commento…"><button class="btn small">Invia</button></div>`;
  const inp = box.querySelector("input"), btn = box.querySelector("button");
  const send = () => {
    const t = inp.value.trim(); if (!t) return;
    p.comments.push({ name: state.me.name || "Tu", text: t, ts: Date.now() }); save();
    paintComments(p, box, card);
    const span = card.querySelector("[data-cmt] span"); if (span) span.textContent = p.comments.length;
  };
  btn.onclick = send;
  inp.onkeydown = e => { if (e.key === "Enter") send(); };
}
// Engagement simulato sui post dell'utente (con backend: like/commenti reali + push).
function simulateEngagement(postId) {
  setTimeout(() => {
    const p = (state.posts || []).find(x => x.id === postId); if (!p) return;
    normReactions(p);
    const r = REACTIONS[Math.floor(Math.random() * REACTIONS.length)];
    p.reactions[r] = (p.reactions[r] || 0) + 1 + Math.floor(Math.random() * 3);
    const who = SEED_PROFILES[Math.floor(Math.random() * SEED_PROFILES.length)];
    save(); notify(r, `${who.name.split(" ")[0]} ha reagito ${r} al tuo post.`, { view: "feed" });
    if (currentView === "feed") renderFeedBody();
  }, 2200);
  setTimeout(() => {
    const p = (state.posts || []).find(x => x.id === postId); if (!p) return;
    const who = SEED_PROFILES[Math.floor(Math.random() * SEED_PROFILES.length)];
    const lines = ["Grande! 🔥", "Anch'io ci sono 🙌", "Bellissimo, fatemi sapere!", "Che invidia 😍", "Spacca 🤘"];
    p.comments = p.comments || []; p.comments.push({ name: who.name, text: lines[Math.floor(Math.random() * lines.length)], ts: Date.now() });
    save(); notify("💬", `${who.name.split(" ")[0]} ha commentato il tuo post.`, { view: "feed" });
    if (currentView === "feed") renderFeedBody();
  }, 5200);
}

// ------------------------------------------------------------- Mappa jam (#9)
// Accesso ibrido (deciso): l'autore sceglie 'open' (idonei entrano subito) o
// 'approval' (richiesta → conferma dell'host).
const SEED_JAMS = [
  { id: "j1", hostId: "u7", host: "Tommaso Riva", avatar: "🎷", color: GRADS[5], title: "Jam jazz al parco", date: "2026-06-22", time: "18:30", place: "Parco Sempione", x: 38, y: 40, genres: ["Jazz", "Funk"], instruments: ["Sax", "Pianoforte", "Basso", "Batteria"], minLevel: 2, accessMode: "open", participants: [{ name: "Tommaso", status: "joined" }, { name: "Sara", status: "joined" }] },
  { id: "j2", hostId: "u1", host: "Marco Bassani", avatar: "🎸", color: GRADS[0], title: "Prove rock aperte", date: "2026-06-25", time: "21:00", place: "Sala Lambrate", x: 66, y: 28, genres: ["Rock", "Blues"], instruments: ["Basso", "Batteria", "Voce"], minLevel: 1, accessMode: "approval", participants: [{ name: "Marco", status: "joined" }] },
  { id: "j3", hostId: "u4", host: "Sara Lombardi", avatar: "🎹", color: GRADS[1], title: "Aperitivo in acustico", date: "2026-06-28", time: "19:00", place: "Navigli", x: 28, y: 72, genres: ["Pop", "Cantautorato"], instruments: ["Chitarra", "Voce", "Violino"], minLevel: 0, accessMode: "open", participants: [{ name: "Sara", status: "joined" }] },
  { id: "j4", hostId: "u11", host: "Paolo De Santis", avatar: "🎺", color: GRADS[2], title: "Sezione fiati funk", date: "2026-07-02", time: "20:30", place: "Isola", x: 74, y: 60, genres: ["Funk", "Soul"], instruments: ["Sax", "Tromba", "Tastiere"], minLevel: 3, accessMode: "approval", participants: [{ name: "Paolo", status: "joined" }] }
];
function allJams() { return [...(state.jams || []), ...SEED_JAMS]; }
function jamEligible(j) {
  const me = state.me, lv = levelsOf(me), wants = j.instruments || [];
  if (!wants.length) return true;
  return wants.some(i => (me.instruments || []).includes(i) && levelRank(lv[i] || me.level) >= (j.minLevel || 0));
}
function myJamStatus(j) { const p = (j.participants || []).find(x => x.me); return p ? p.status : null; }
function rerenderBoardMap() { if (currentView === "board") renderBoard2(); }

function renderJamMap(box) {
  const jams = allJams();
  box.appendChild(el(`<div>
    <p class="view-sub">Jam vicino a te. In <span style="color:var(--ok);font-weight:800">verde</span> quelle adatte ai tuoi strumenti e livello. Tocca un segnaposto.</p>
    <div class="jam-map" id="jamMap"><div class="jam-me" title="Sei qui">📍</div></div>
    <div class="section-label">Tutte le jam</div>
    <div id="jamList"></div>
  </div>`));
  const map = $("#jamMap");
  jams.forEach(j => {
    const pin = el(`<button class="jam-pin${jamEligible(j) ? " ok" : ""}" style="left:${j.x}%;top:${j.y}%" title="${esc(j.title)}">${j.avatar}</button>`);
    pin.onclick = () => openJamSheet(j);
    map.appendChild(pin);
  });
  const list = $("#jamList");
  jams.forEach(j => list.appendChild(jamCard(j)));
}
function jamCard(j) {
  const elig = jamEligible(j), my = myJamStatus(j);
  const c = el(`<div class="card">
    <div class="card-head">${avatarTag({ avatar: j.avatar, color: j.color })}<div class="meta">
      <div class="name">${esc(j.title)} ${elig ? '<span class="tag lvl">adatta a te</span>' : ""}</div>
      <div class="loc">📅 ${formatDate(j.date)} · ${esc(j.time)} · 📍 ${esc(j.place)}</div></div>
      ${j.accessMode === "approval" ? '<span class="tag">🔒 su richiesta</span>' : '<span class="tag accent">aperta</span>'}</div>
    <div class="tags" style="margin-top:8px">${(j.instruments || []).map(i => `<span class="tag">${esc(i)}</span>`).join("")}</div>
    ${my ? `<div class="aff-note" style="margin-top:8px">${my === "joined" ? "✓ Partecipi a questa jam" : "⏳ Richiesta inviata"}</div>` : ""}
  </div>`);
  c.onclick = () => openJamSheet(j);
  return c;
}
function jamActionHtml(j, elig, my) {
  if (j.hostId === "me") return `<div class="aff-note" style="margin-top:14px">Sei l'host di questa jam.</div>`;
  if (my === "joined") return `<button class="btn secondary" id="jamCancel" style="margin-top:14px">Annulla partecipazione</button>`;
  if (my === "requested") return `<button class="btn secondary" id="jamCancel" style="margin-top:14px">Annulla richiesta</button>`;
  if (!elig) return `<div class="aff-note" style="margin-top:14px">⚠️ Non risulti idoneo: servono <b>${(j.instruments || []).join(", ")}</b> a livello <b>${esc(LEVELS[j.minLevel || 0])}+</b>. Aggiorna i tuoi strumenti nel profilo.</div>`;
  return `<button class="btn" id="jamAct" style="margin-top:14px">${j.accessMode === "approval" ? "📨 Richiedi di partecipare" : "🎶 Partecipa"}</button>`;
}
function openJamSheet(j) {
  const elig = jamEligible(j), my = myJamStatus(j), isHost = j.hostId === "me";
  const reqs = (j.participants || []).filter(p => p.status === "requested" && !p.me);
  openModal(`
    <div style="text-align:center"><div style="display:flex;justify-content:center">${avatarTag({ avatar: j.avatar, color: j.color }, true)}</div>
      <h2>${esc(j.title)}</h2>
      <div class="loc">📅 ${formatDate(j.date)} · ${esc(j.time)} · 📍 ${esc(j.place)}</div>
      <div class="loc" style="margin-top:4px">Host: ${esc(j.host)}</div>
    </div>
    <div class="tags" style="justify-content:center;margin-top:10px">${(j.genres || []).map(g => `<span class="tag accent">${esc(g)}</span>`).join("")}</div>
    <div class="section-label">Strumenti cercati · livello min. ${esc(LEVELS[j.minLevel || 0])}</div>
    <div class="tags">${(j.instruments || []).map(i => `<span class="tag">${esc(i)}</span>`).join("")}</div>
    <div class="section-label">Partecipanti (${(j.participants || []).length})</div>
    <div class="tags">${(j.participants || []).map(p => `<span class="tag${p.status === "joined" ? " lvl" : ""}">${esc(p.name)}${p.status === "requested" ? " ⏳" : ""}</span>`).join("")}</div>
    <div class="aff-note" style="margin-top:12px">${j.accessMode === "approval" ? "🔒 Jam <b>su approvazione</b>: l'host conferma le richieste." : "✅ Jam <b>aperta</b>: gli idonei entrano subito."}</div>
    ${isHost && reqs.length ? `<div class="section-label">Richieste</div><div id="jamReqs">${reqs.map((p, i) => `<div class="lvl-row"><span class="lvl-inst">${esc(p.name)}</span><span><button class="btn small" data-ok="${i}">✓ Accetta</button> <button class="btn small secondary" data-no="${i}">✕</button></span></div>`).join("")}</div>` : ""}
    ${jamActionHtml(j, elig, my)}
    ${!isHost && j.hostId ? `<button class="btn secondary" id="jamDm" style="margin-top:10px">✉️ Scrivi a ${esc(j.host.split(" ")[0])}</button>` : ""}
  `);
  if ($("#jamDm")) $("#jamDm").onclick = () => { closeModal(); dmAuthor(j.hostId, j.host); };
  if ($("#jamAct")) $("#jamAct").onclick = () => jamJoin(j);
  if ($("#jamCancel")) $("#jamCancel").onclick = () => { j.participants = (j.participants || []).filter(x => !x.me); save(); closeModal(); toast("Annullato"); rerenderBoardMap(); };
  if (isHost && reqs.length) {
    document.querySelectorAll("#jamReqs [data-ok]").forEach(b => b.onclick = () => { reqs[+b.dataset.ok].status = "joined"; save(); toast("Richiesta accettata ✓"); openJamSheet(j); rerenderBoardMap(); });
    document.querySelectorAll("#jamReqs [data-no]").forEach(b => b.onclick = () => { const p = reqs[+b.dataset.no]; j.participants = j.participants.filter(x => x !== p); save(); toast("Richiesta rifiutata"); openJamSheet(j); rerenderBoardMap(); });
  }
}
function jamJoin(j) {
  const status = j.accessMode === "approval" ? "requested" : "joined";
  j.participants = j.participants || [];
  j.participants.push({ name: state.me.name || "Tu", status, me: true });
  save(); closeModal();
  if (status === "joined") { toast("Partecipi alla jam! 🎶"); notify("🎶", `Partecipi a "${j.title}" il ${formatDate(j.date)}.`, { view: "board" }); }
  else {
    toast("Richiesta inviata 📨"); notify("⏳", `Richiesta inviata per "${j.title}".`, { view: "board" });
    setTimeout(() => {
      const me = (j.participants || []).find(x => x.me);
      if (me && me.status === "requested") { me.status = "joined"; save(); notify("✅", `${j.host.split(" ")[0]} ha accettato la tua richiesta per "${j.title}"!`, { view: "board" }); rerenderBoardMap(); }
    }, 3200);
  }
  rerenderBoardMap();
}
function openCreateJam() {
  openModal(`
    <h2>Crea una jam 🎶</h2>
    <label class="field">Titolo</label><input type="text" id="jTitle" placeholder="Es. Jam blues al parco">
    <label class="field" style="margin-top:10px">Luogo</label><input type="text" id="jPlace" value="${esc(state.me.city)}" placeholder="Es. Parco Sempione">
    <div class="filter-row" style="margin-top:10px">
      <div style="flex:1"><label class="field">Data</label><input type="date" id="jDate"></div>
      <div style="flex:1"><label class="field">Ora</label><input type="time" id="jTime" value="19:00"></div>
    </div>
    <label class="field" style="margin-top:10px">Generi</label><div class="chips" id="jGen">${chips(GENRES, [])}</div>
    <label class="field" style="margin-top:10px">Strumenti cercati</label><div class="chips" id="jIns">${chips(INSTRUMENTS, [])}</div>
    <label class="field" style="margin-top:10px">Livello minimo</label><select id="jLvl">${options(LEVELS, LEVELS[0])}</select>
    <label class="field" style="margin-top:10px">Accesso</label>
    <select id="jAccess"><option value="open">Aperta — gli idonei entrano subito</option><option value="approval">Su approvazione — confermi tu</option></select>
    <button class="btn" id="jSave" style="margin-top:16px">Pubblica jam</button>
  `);
  const selG = [], selI = [];
  document.querySelectorAll("#jGen .chip").forEach(c => c.onclick = () => toggleChip(c, selG));
  document.querySelectorAll("#jIns .chip").forEach(c => c.onclick = () => toggleChip(c, selI));
  $("#jSave").onclick = () => {
    const title = $("#jTitle").value.trim(); if (!title) return toast("Dai un titolo alla jam");
    if (!selI.length) return toast("Indica almeno uno strumento cercato");
    const j = {
      id: "mj" + Date.now(), hostId: "me", host: state.me.name || "Tu", avatar: state.me.avatar, color: state.me.color,
      title, place: $("#jPlace").value.trim() || state.me.city, date: $("#jDate").value || new Date(Date.now() + 5 * 864e5).toISOString().slice(0, 10),
      time: $("#jTime").value || "19:00", genres: selG, instruments: selI, minLevel: LEVELS.indexOf($("#jLvl").value),
      accessMode: $("#jAccess").value, x: 30 + Math.floor(Math.random() * 40), y: 28 + Math.floor(Math.random() * 44),
      participants: [{ name: state.me.name || "Tu", status: "joined", me: true }]
    };
    state.jams = state.jams || []; state.jams.unshift(j); save(); closeModal(); toast("Jam pubblicata 🎶");
    state.ui.boardMode = "map"; if (currentView === "board") renderBoard2(); else navigate("board");
    setTimeout(() => {
      const jj = (state.jams || []).find(x => x.id === j.id); if (!jj) return;
      const who = SEED_PROFILES[Math.floor(Math.random() * SEED_PROFILES.length)];
      jj.participants.push({ name: who.name, status: j.accessMode === "approval" ? "requested" : "joined" }); save();
      notify(j.accessMode === "approval" ? "🙋" : "🎶", `${who.name.split(" ")[0]} ${j.accessMode === "approval" ? "ha chiesto di partecipare a" : "si è unito a"} "${j.title}".`, { view: "board" });
      rerenderBoardMap();
    }, 3500);
  };
}

// ------------------------------------------------------------- Lezioni (#12)
// Deciso: prenotazione + pagamento online da subito (qui simulato).
const SEED_TEACHERS = [
  { id: "t1", name: "Sara Lombardi", avatar: "🎹", color: GRADS[1], instruments: ["Pianoforte", "Tastiere"], city: "Milano", online: true, hourly: 35, bio: "Pianista jazz/pop, 10 anni di insegnamento. Metodo su misura, dai principianti agli avanzati.", rating: 49, ratings: 23, slots: [{ id: "s1", date: "2026-06-23", time: "17:00" }, { id: "s2", date: "2026-06-23", time: "18:00" }, { id: "s3", date: "2026-06-25", time: "16:00" }] },
  { id: "t2", name: "Marco Bassani", avatar: "🎸", color: GRADS[0], instruments: ["Chitarra elettrica", "Chitarra"], city: "Milano", online: false, hourly: 30, bio: "Chitarra rock/blues: dai primi accordi al primo assolo.", rating: 47, ratings: 15, slots: [{ id: "s4", date: "2026-06-24", time: "19:00" }, { id: "s5", date: "2026-06-26", time: "18:30" }] },
  { id: "t3", name: "Elena Marchi", avatar: "🎻", color: GRADS[2], instruments: ["Violino"], city: "Milano", online: true, hourly: 40, bio: "Violino classico e moderno, formazione di conservatorio.", rating: 50, ratings: 31, slots: [{ id: "s6", date: "2026-06-23", time: "15:00" }, { id: "s7", date: "2026-06-27", time: "11:00" }] },
  { id: "t4", name: "Tommaso Riva", avatar: "🎷", color: GRADS[5], instruments: ["Sax"], city: "Milano", online: false, hourly: 32, bio: "Sax jazz e funk: improvvisazione, teoria e tanto groove.", rating: 46, ratings: 9, slots: [{ id: "s8", date: "2026-06-25", time: "20:00" }] }
];
function allTeachers() {
  const mine = state.teacher ? [Object.assign({ id: "me", name: state.me.name || "Tu", avatar: state.me.avatar, color: state.me.color, photo: state.me.photo || "", mine: true, rating: 0, ratings: 0 }, state.teacher)] : [];
  return [...mine, ...SEED_TEACHERS];
}
function renderLessons(box) {
  const myBk = state.lessonBookings || [];
  box.appendChild(el(`<div>
    <p class="view-sub">Trova un insegnante, prenoti e <b>paghi online</b> (pagamento simulato in questo prototipo).</p>
    <div class="card flat">
      <div class="row-between"><b>🎓 Insegni uno strumento?</b>${state.teacher ? '<span class="tag lvl">attivo</span>' : '<span class="badge-new">novità</span>'}</div>
      <p class="view-sub" style="margin:8px 0 10px">Pubblica le tue disponibilità a calendario e ricevi prenotazioni pagate.</p>
      <button class="btn small" id="beTeacher">${state.teacher ? "Gestisci le mie disponibilità" : "Diventa insegnante"}</button>
    </div>
    ${myBk.length ? `<div class="section-label">Le mie lezioni prenotate</div><div id="myLessons"></div>` : ""}
    <div class="section-label">Insegnanti vicino a te</div>
    <div id="teacherList"></div>
  </div>`));
  $("#beTeacher").onclick = () => openTeacherSheet();
  if (myBk.length) { const ml = $("#myLessons"); myBk.forEach(b => ml.appendChild(lessonBookingRow(b))); }
  const tl = $("#teacherList"); allTeachers().forEach(t => tl.appendChild(teacherCard(t)));
}
function lessonBookingRow(b) {
  return el(`<div class="card flat" style="margin-bottom:8px">
    <div class="card-head">${avatarTag(b)}<div class="meta">
      <div class="name">${esc(b.teacherName)} <span class="tag lvl">${b.status === "confirmed" ? "confermata" : esc(b.status)}</span></div>
      <div class="loc">📅 ${formatDate(b.date)} · ${esc(b.time)} · 💶 ${b.amount}€ (pagati · simulato)</div></div></div>
  </div>`);
}
function teacherCard(t) {
  const free = (t.slots || []).filter(s => !s.booked).length;
  const c = el(`<div class="card">
    <div class="card-head">${avatarTag(t)}<div class="meta">
      <div class="name">${esc(t.name)} ${t.mine ? '<span class="tag">tu</span>' : `<span class="score">★ ${(t.rating / 10).toFixed(1)}</span>`}</div>
      <div class="loc">${(t.instruments || []).join(", ")} · 📍 ${esc(t.city)}${t.online ? " · 💻 online" : ""}</div></div>
      <div style="text-align:right;font-weight:800;color:var(--accent)">${t.hourly}€<br><small style="color:var(--muted);font-weight:600">/ ora</small></div></div>
    <div class="loc" style="margin-top:8px">🗓️ ${free} slot liber${free === 1 ? "o" : "i"}</div>
  </div>`);
  c.onclick = () => openTeacherProfile(t);
  return c;
}
function openTeacherProfile(t) {
  const free = (t.slots || []).filter(s => !s.booked);
  openModal(`
    <div style="text-align:center"><div style="display:flex;justify-content:center">${avatarTag(t, true)}</div>
      <h2>${esc(t.name)}</h2>
      <div class="loc">${(t.instruments || []).join(", ")} · 📍 ${esc(t.city)}${t.online ? " · 💻 online" : ""}</div>
      <div style="margin-top:6px;font-weight:800;color:var(--accent)">${t.hourly}€ / ora</div>
    </div>
    ${t.bio ? `<div class="section-label">Su di me</div><p style="margin:0;line-height:1.5">${esc(t.bio)}</p>` : ""}
    <div class="section-label">Disponibilità</div>
    ${free.length ? `<div id="slotPick" class="slot-grid">${free.map(s => `<button class="slot-btn" data-slot="${esc(s.id)}">📅 ${formatDate(s.date)}<br>${esc(s.time)}</button>`).join("")}</div>` : `<div class="aff-note">Nessuno slot libero al momento.</div>`}
    ${t.mine ? `<div class="aff-note" style="margin-top:12px">Questo è il tuo profilo insegnante.</div>` : ""}
  `);
  if (!t.mine) document.querySelectorAll("#slotPick .slot-btn").forEach(b => b.onclick = () => { const s = (t.slots || []).find(x => x.id === b.dataset.slot); if (s) openBookLesson(t, s); });
}
function openBookLesson(t, s) {
  const fee = t.hourly, comm = Math.round(fee * 0.1);
  openModal(`
    <h2>Prenota lezione 🎓</h2>
    <div class="aff-note">${esc(t.name)} · 📅 ${formatDate(s.date)} · ${esc(s.time)}</div>
    <div class="card flat" style="margin-top:12px">
      <div class="row-between"><span>Lezione (1 ora)</span><b>${fee}€</b></div>
      <div class="row-between"><span class="loc">di cui commissione JamMate (10%)</span><span class="loc">${comm}€</span></div>
    </div>
    <div class="aff-note" style="margin-top:10px">💳 Pagamento <b>simulato</b> in questo prototipo (in produzione: carta via Stripe, importo in escrow fino alla lezione).</div>
    <button class="btn" id="payLesson" style="margin-top:14px">💳 Paga ${fee}€ e prenota</button>
  `);
  $("#payLesson").onclick = () => {
    s.booked = true;
    const bk = { id: "lb" + Date.now(), teacherId: t.id, teacherName: t.name, avatar: t.avatar, color: t.color, date: s.date, time: s.time, amount: fee, status: "confirmed" };
    state.lessonBookings = state.lessonBookings || []; state.lessonBookings.unshift(bk); save();
    closeModal(); toast("Lezione prenotata e pagata ✓");
    notify("🎓", `Lezione con ${t.name.split(" ")[0]} confermata: ${formatDate(s.date)} alle ${s.time}.`, { view: "palco" });
    rerenderPalco();
  };
}
function openTeacherSheet() {
  const t = state.teacher;
  openModal(`
    <h2>${t ? "Le mie disponibilità" : "Diventa insegnante"} 🎓</h2>
    <label class="field">Strumenti che insegni</label><div class="chips" id="teIns">${chips(INSTRUMENTS, t ? t.instruments : [])}</div>
    <label class="field" style="margin-top:10px">Tariffa oraria (€)</label><input type="number" id="teFee" value="${t ? t.hourly : 30}" min="5">
    <label class="field" style="margin-top:10px">Presentazione</label><textarea id="teBio" placeholder="Esperienza, metodo, livelli che segui…">${t ? esc(t.bio) : ""}</textarea>
    <label class="field" style="margin-top:10px;display:flex;align-items:center;gap:8px"><input type="checkbox" id="teOnline" ${t && t.online ? "checked" : ""}> Disponibile anche online</label>
    <div class="section-label">Aggiungi uno slot a calendario</div>
    <div class="filter-row">
      <input type="date" id="teDate"><input type="time" id="teTime" value="18:00">
      <button class="btn small" id="teAddSlot">＋</button>
    </div>
    <div id="teSlots" style="margin-top:8px"></div>
    <button class="btn" id="teSave" style="margin-top:16px">${t ? "Salva" : "Pubblica profilo insegnante"}</button>
  `);
  const selI = t ? t.instruments.slice() : [];
  const slots = t ? (t.slots || []).map(s => Object.assign({}, s)) : [];
  document.querySelectorAll("#teIns .chip").forEach(c => c.onclick = () => toggleChip(c, selI));
  const paintSlots = () => {
    const box = $("#teSlots");
    box.innerHTML = slots.length ? slots.map((s, i) => `<div class="lvl-row"><span class="lvl-inst">📅 ${formatDate(s.date)} · ${esc(s.time)}${s.booked ? " · prenotato" : ""}</span>${s.booked ? "" : `<button class="rep-del" data-i="${i}">✕</button>`}</div>`).join("") : `<p class="view-sub">Nessuno slot. Aggiungine almeno uno.</p>`;
    box.querySelectorAll("[data-i]").forEach(b => b.onclick = () => { slots.splice(+b.dataset.i, 1); paintSlots(); });
  };
  paintSlots();
  $("#teAddSlot").onclick = () => { const d = $("#teDate").value, tm = $("#teTime").value; if (!d) return toast("Scegli una data"); slots.push({ id: "ms" + Date.now() + Math.random().toString(36).slice(2, 5), date: d, time: tm || "18:00" }); paintSlots(); };
  $("#teSave").onclick = () => {
    if (!selI.length) return toast("Indica almeno uno strumento");
    state.teacher = { instruments: selI, hourly: +$("#teFee").value || 30, bio: $("#teBio").value.trim(), online: $("#teOnline").checked, slots };
    save(); closeModal(); toast(t ? "Disponibilità salvate ✓" : "Sei un insegnante su JamMate! 🎓"); rerenderPalco();
  };
}

// ------------------------------------------------------------- Export globali
window.renderFeed = renderFeed;
window.renderJamMap = renderJamMap;
window.renderLessons = renderLessons;
window.openCreateJam = openCreateJam;
window.openNotifications = openNotifications;
window.notify = notify;
