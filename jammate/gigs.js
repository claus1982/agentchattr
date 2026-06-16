/* JamMate — FASE 1: Palco (marketplace band ↔ locali)
 * Prenotazione con conferma, recensioni a due lati verificate, pagamenti SIMULATI.
 * Usa gli helper globali definiti in app.js ($,el,esc,openModal,toast,avatarTag,
 * save,state,navigate,formatDate,GENRES,INSTRUMENTS,options,chips,toggleChip,currentView).
 * Reso modulare apposta: in futuro questo diventa il "modulo booking" estraibile. */

const STATUS = {
  requested: { t: "In attesa del preventivo", c: "warn" },
  quoted: { t: "Preventivo ricevuto", c: "accent" },
  confirmed: { t: "Confermata ✓", c: "ok" },
  completed: { t: "Serata completata", c: "accent" },
  reviewed: { t: "Recensita ⭐", c: "ok" }
};

function allVenues() { return [...(state.myVenue ? [Object.assign({ mine: true }, state.myVenue)] : []), ...SEED_VENUES]; }
function myBand() { return (state.bands || [])[0] || null; }
function stars(r) { return "★ " + (r / 10).toFixed(1); }
function bookingsPending() { return (state.bookings || []).filter(b => b.status !== "reviewed").length; }

// --------------------------------------------------- Vista Palco
function renderPalco(app) {
  const seg = state.ui.palcoMode || "band";
  app.appendChild(el(`<div>
    <div class="row-between"><h1 class="view-title">Palco 🎤</h1>
      <button class="btn small secondary" id="bookingsBtn">📋 Prenotazioni${bookingsPending() ? " · " + bookingsPending() : ""}</button></div>
    <p class="view-sub">Band che si offrono per serate, e locali che cercano musica. Prenotazione con conferma e recensioni a due lati.</p>
    <div class="segmented">
      <button data-m="band" class="${seg === "band" ? "on" : ""}">🎸 La mia band</button>
      <button data-m="venue" class="${seg === "venue" ? "on" : ""}">🏢 Sono un locale</button>
    </div>
    <div id="palcoBody"></div>
  </div>`));
  app.querySelectorAll(".segmented button").forEach(b => b.onclick = () => { state.ui.palcoMode = b.dataset.m; save(); rerenderPalco(); });
  $("#bookingsBtn").onclick = openBookings;
  if (seg === "band") renderBandSide($("#palcoBody")); else renderVenueSide($("#palcoBody"));
}
function rerenderPalco() { if (currentView === "palco") { $("#app").innerHTML = ""; renderPalco($("#app")); } }

// --------------------------------------------------- Lato "La mia band"
function renderBandSide(box) {
  const band = myBand();
  if (!band) {
    box.appendChild(el(`<div class="empty">Non hai ancora registrato una band.<br>Creane una per offrirti alle serate locali. 🎸</div>`));
    const b = el(`<button class="btn">＋ Crea la tua band</button>`); b.onclick = openCreateBand; box.appendChild(b);
    return;
  }
  // Card band con badge "Pronta & Disponibile"
  const ready = band.available && (band.repertoire || []).length && band.genres.length;
  const c = el(`<div class="card flat">
    <div class="card-head">${avatarTag(band)}<div class="meta">
      <div class="name">${esc(band.name)} ${ready ? '<span class="tag lvl">✓ Pronta & Disponibile</span>' : '<span class="tag">bozza</span>'}</div>
      <div class="loc">📍 ${esc(band.city)} · ${band.members.length} elementi · 💶 ${esc(band.fee || "—")}</div>
    </div></div>
    <div class="tags">${band.genres.map(g => `<span class="tag accent">${esc(g)}</span>`).join("")}</div>
    <div class="row-between" style="margin-top:12px">
      <label style="display:flex;align-items:center;gap:8px;font-size:.9rem"><input type="checkbox" id="availTgl" ${band.available ? "checked" : ""}> Disponibile per serate</label>
      <button class="btn small secondary" id="editBand">Modifica EPK</button>
    </div>
  </div>`);
  box.appendChild(c);
  $("#availTgl").onchange = e => { band.available = e.target.checked; save(); rerenderPalco(); };
  $("#editBand").onclick = () => openCreateBand(band);

  box.appendChild(el(`<div class="section-label">Locali che cercano una band</div>`));
  SEED_VENUES.forEach(v => box.appendChild(venueOpenCard(v, band)));
}

function venueOpenCard(v, band) {
  const c = el(`<div class="card">
    <div class="card-head">${avatarTag(v)}<div class="meta">
      <div class="name">${esc(v.name)} <span class="score">${stars(v.rating)}</span></div>
      <div class="loc">${esc(v.type)} · 📍 ${esc(v.city)} · cap. ${v.capacity}</div>
    </div></div>
    <div class="card" style="margin:10px 0 0;cursor:default;background:rgba(255,255,255,.03)">
      <div class="event-date">📅 ${formatDate(v.openNight.date)} · cerca: ${esc(v.openNight.genre)}</div>
      <div class="loc" style="margin-top:4px">💶 Budget: ${esc(v.openNight.budget)}</div>
    </div>
  </div>`);
  c.onclick = () => openVenueSheet(v, band);
  return c;
}

// --------------------------------------------------- Lato "Sono un locale"
function renderVenueSide(box) {
  const v = state.myVenue;
  if (!v) {
    box.appendChild(el(`<div class="empty">Hai un locale o organizzi eventi?<br>Crea il profilo per cercare e prenotare band. 🏢</div>`));
    const b = el(`<button class="btn">＋ Crea profilo locale</button>`); b.onclick = openCreateVenue; box.appendChild(b);
    return;
  }
  const c = el(`<div class="card flat">
    <div class="card-head">${avatarTag(v)}<div class="meta">
      <div class="name">${esc(v.name)}</div><div class="loc">${esc(v.type)} · 📍 ${esc(v.city)} · cap. ${v.capacity}</div>
    </div><button class="btn small secondary" id="editVenue">Modifica</button></div>
    <div class="tags">${(v.genres || []).map(g => `<span class="tag accent">${esc(g)}</span>`).join("")}</div>
  </div>`);
  box.appendChild(c);
  $("#editVenue").onclick = () => openCreateVenue(v);

  box.appendChild(el(`<div class="section-label">Band pronte e disponibili</div>`));
  SEED_BANDS.forEach(b => box.appendChild(bandHireCard(b, v)));
}

function bandHireCard(b, venue) {
  const c = el(`<div class="card">
    <div class="card-head">${avatarTag(b)}<div class="meta">
      <div class="name">${esc(b.name)} <span class="score">${stars(b.rating)}</span> ${b.available ? '<span class="tag lvl">disponibile</span>' : '<span class="tag">occupata</span>'}</div>
      <div class="loc">📍 ${esc(b.city)} · ${b.members.length} elementi · 💶 ${esc(b.fee)}</div>
    </div></div>
    <div class="tagline" style="margin:8px 0 0;font-style:italic;color:var(--muted)">“${esc(b.tagline)}”</div>
    <div class="tags" style="margin-top:8px">${b.genres.map(g => `<span class="tag">${esc(g)}</span>`).join("")}</div>
  </div>`);
  c.onclick = () => openBandSheet(b, venue);
  return c;
}

// --------------------------------------------------- EPK band (vista) + azione locale
function openBandSheet(b, venue) {
  openModal(`
    <div style="text-align:center"><div style="display:flex;justify-content:center">${avatarTag(b, true)}</div>
      <h2>${esc(b.name)}</h2>
      <div class="loc">📍 ${esc(b.city)} · ${b.members.length} elementi · <span class="score">${stars(b.rating)}</span> (${b.ratings})</div>
      <div style="margin-top:6px;font-weight:800;color:var(--accent)">💶 ${esc(b.fee)} / serata</div>
    </div>
    <div class="tags" style="justify-content:center;margin-top:10px">${b.genres.map(g => `<span class="tag accent">${esc(g)}</span>`).join("")}</div>
    <div class="section-label">Formazione</div><div class="tags">${b.members.map(m => `<span class="tag">${esc(m)}</span>`).join("")}</div>
    <div class="section-label">Repertorio (estratto)</div>
    ${(b.repertoire || []).map(s => `<div class="rep-item"><span class="song">${esc(s)}</span></div>`).join("")}
    <div class="section-label">Recensioni verificate</div>
    <div class="aff-note">⭐ ${stars(b.rating)} su ${b.ratings} serate verificate. "Puntuali, professionali, hanno fatto ballare tutti." — un locale</div>
    ${venue ? `<button class="btn" id="reqBtn" style="margin-top:18px">📅 Richiedi una prenotazione</button>` : `<div class="aff-note" style="margin-top:16px">Crea un profilo locale per prenotare questa band.</div>`}
  `);
  if (venue) $("#reqBtn").onclick = () => { closeModal(); openRequestSheet(b, venue); };
}

// EPK locale (vista) + azione band
function openVenueSheet(v, band) {
  openModal(`
    <div style="text-align:center"><div style="display:flex;justify-content:center">${avatarTag(v, true)}</div>
      <h2>${esc(v.name)}</h2>
      <div class="loc">${esc(v.type)} · 📍 ${esc(v.city)} · cap. ${v.capacity} · <span class="score">${stars(v.rating)}</span></div>
    </div>
    <div class="tags" style="justify-content:center;margin-top:10px">${v.genres.map(g => `<span class="tag accent">${esc(g)}</span>`).join("")}</div>
    <div class="section-label">Serata cercata</div>
    <div class="card flat" style="background:rgba(255,255,255,.03)">
      <div class="event-date">📅 ${formatDate(v.openNight.date)}</div>
      <div class="loc" style="margin-top:4px">🎵 ${esc(v.openNight.genre)} · 💶 ${esc(v.openNight.budget)}</div>
    </div>
    ${band ? `<button class="btn" id="propBtn" style="margin-top:18px">🎸 Proponi “${esc(band.name)}” per questa serata</button>` : `<div class="aff-note" style="margin-top:16px">Crea la tua band per proporti.</div>`}
  `);
  if (band) $("#propBtn").onclick = () => { closeModal(); openProposeSheet(v, band); };
}

// --------------------------------------------------- Creazione band / locale
function openCreateBand(existing) {
  const b = existing || {};
  openModal(`
    <h2>${existing ? "Modifica" : "Crea la"} band 🎸</h2>
    <label class="field">Nome della band</label><input type="text" id="bName" value="${esc(b.name || "")}" placeholder="Es. The Riffs">
    <label class="field" style="margin-top:10px">Città</label><input type="text" id="bCity" value="${esc(b.city || state.me.city)}">
    <label class="field" style="margin-top:10px">Compenso indicativo / serata</label><input type="text" id="bFee" value="${esc(b.fee || "")}" placeholder="Es. 400€">
    <label class="field" style="margin-top:10px">Frase a effetto</label><input type="text" id="bTag" value="${esc(b.tagline || "")}" placeholder="Es. Cover anni 80, energia pura">
    <label class="field" style="margin-top:10px">Generi</label><div class="chips" id="bGen">${chips(GENRES, b.genres || [])}</div>
    <label class="field" style="margin-top:10px">Formazione</label><div class="chips" id="bMem">${chips(INSTRUMENTS, b.members || [])}</div>
    <label class="field" style="margin-top:10px">Repertorio (un brano per riga)</label>
    <textarea id="bRep" placeholder="Wonderwall&#10;Hotel California">${esc((b.repertoire || []).join("\n"))}</textarea>
    <button class="btn" id="bSave" style="margin-top:16px">${existing ? "Salva" : "Crea band"}</button>
  `);
  const selG = (b.genres || []).slice(), selM = (b.members || []).slice();
  document.querySelectorAll("#bGen .chip").forEach(c => c.onclick = () => toggleChip(c, selG));
  document.querySelectorAll("#bMem .chip").forEach(c => c.onclick = () => toggleChip(c, selM));
  $("#bSave").onclick = () => {
    const name = $("#bName").value.trim(); if (!name) return toast("Dai un nome alla band");
    if (!selM.length) return toast("Seleziona almeno uno strumento della formazione");
    const band = Object.assign(existing || { id: "mb" + Date.now(), avatar: "🎸", color: GRADS[Math.floor(Math.random() * GRADS.length)], rating: 0, ratings: 0, available: true }, {
      name, city: $("#bCity").value.trim() || state.me.city, fee: $("#bFee").value.trim(), tagline: $("#bTag").value.trim(),
      genres: selG, members: selM, repertoire: $("#bRep").value.split("\n").map(s => s.trim()).filter(Boolean)
    });
    if (!existing) state.bands = [band]; save(); closeModal(); toast("Band salvata 🎸"); rerenderPalco();
  };
}

function openCreateVenue(existing) {
  const v = existing || {};
  const TYPES = ["Pub", "Jazz club", "Ristorante", "Sala eventi", "Circolo", "Azienda", "Privato"];
  openModal(`
    <h2>${existing ? "Modifica" : "Crea"} profilo locale 🏢</h2>
    <label class="field">Nome locale / azienda</label><input type="text" id="vName" value="${esc(v.name || "")}" placeholder="Es. Pub The Anchor">
    <label class="field" style="margin-top:10px">Tipo</label><select id="vType">${options(TYPES, v.type || "Pub")}</select>
    <label class="field" style="margin-top:10px">Città</label><input type="text" id="vCity" value="${esc(v.city || state.me.city)}">
    <label class="field" style="margin-top:10px">Capienza</label><input type="text" id="vCap" value="${esc(v.capacity || "")}" placeholder="Es. 80">
    <label class="field" style="margin-top:10px">Generi graditi</label><div class="chips" id="vGen">${chips(GENRES, v.genres || [])}</div>
    <button class="btn" id="vSave" style="margin-top:16px">${existing ? "Salva" : "Crea profilo"}</button>
  `);
  const selG = (v.genres || []).slice();
  document.querySelectorAll("#vGen .chip").forEach(c => c.onclick = () => toggleChip(c, selG));
  $("#vSave").onclick = () => {
    const name = $("#vName").value.trim(); if (!name) return toast("Dai un nome al locale");
    state.myVenue = Object.assign(existing || { id: "mv" + Date.now(), avatar: "🏢", color: GRADS[1], rating: 0, ratings: 0 }, {
      name, type: $("#vType").value, city: $("#vCity").value.trim(), capacity: $("#vCap").value.trim() || "—", genres: selG
    });
    save(); closeModal(); toast("Profilo locale salvato 🏢"); rerenderPalco();
  };
}

// --------------------------------------------------- Flusso prenotazione
function openProposeSheet(v, band) { // la band propone al locale (con preventivo)
  openModal(`
    <h2>Proponi per la serata</h2>
    <div class="aff-note">${esc(band.name)} → ${esc(v.name)} · 📅 ${formatDate(v.openNight.date)} · budget ${esc(v.openNight.budget)}</div>
    <label class="field" style="margin-top:12px">Il tuo preventivo</label><input type="text" id="pQuote" value="${esc(band.fee || "")}" placeholder="Es. 400€">
    <label class="field" style="margin-top:10px">Messaggio (opzionale)</label><textarea id="pMsg" placeholder="Disponibili, portiamo service audio…"></textarea>
    <button class="btn" id="pSend" style="margin-top:16px">Invia proposta</button>
  `);
  $("#pSend").onclick = () => {
    const quote = $("#pQuote").value.trim() || band.fee || "—";
    const bk = addBooking({ kind: "band", bandId: band.id, bandName: band.name, venueId: v.id, venueName: v.name, venueAvatar: v.avatar, venueColor: v.color, bandAvatar: band.avatar, bandColor: band.color, date: v.openNight.date, budget: v.openNight.budget, quote, status: "quoted" });
    closeModal(); toast("Proposta inviata 📨"); navigate("palco");
    simulate(bk.id, "confirmed", `🎉 ${v.name} ha confermato “${band.name}”!`);
  };
}

function openRequestSheet(b, venue) { // il locale richiede la band
  openModal(`
    <h2>Richiedi prenotazione</h2>
    <div class="aff-note">${esc(venue.name)} → ${esc(b.name)}</div>
    <label class="field" style="margin-top:12px">Data</label><input type="date" id="rDate">
    <label class="field" style="margin-top:10px">Budget proposto</label><input type="text" id="rBudget" placeholder="Es. 400€">
    <label class="field" style="margin-top:10px">Messaggio (opzionale)</label><textarea id="rMsg" placeholder="Serata cover, 2 set da 45 min…"></textarea>
    <button class="btn" id="rSend" style="margin-top:16px">Invia richiesta</button>
  `);
  $("#rSend").onclick = () => {
    const date = $("#rDate").value || new Date(Date.now() + 12 * 864e5).toISOString().slice(0, 10);
    const bk = addBooking({ kind: "venue", bandId: b.id, bandName: b.name, venueId: venue.id, venueName: venue.name, venueAvatar: venue.avatar, venueColor: venue.color, bandAvatar: b.avatar, bandColor: b.color, date, budget: $("#rBudget").value.trim() || "—", quote: b.fee, status: "requested" });
    closeModal(); toast("Richiesta inviata 📨"); navigate("palco");
    simulate(bk.id, "quoted", `💬 ${b.name} ha risposto con un preventivo: ${b.fee}`);
  };
}

function addBooking(data) {
  const bk = Object.assign({ id: "bk" + Date.now() }, data);
  state.bookings = state.bookings || []; state.bookings.unshift(bk); save(); return bk;
}
function simulate(id, status, msg) {
  setTimeout(() => {
    const bk = (state.bookings || []).find(x => x.id === id); if (!bk) return;
    bk.status = status; save(); toast(msg);
    rerenderPalco(); if ($(".modal")) openBookings();
  }, 1600);
}

// --------------------------------------------------- Prenotazioni + recensioni
function openBookings() {
  const list = state.bookings || [];
  const rows = list.length ? list.map(bookingRow).join("") : `<div class="empty">Nessuna prenotazione ancora.</div>`;
  openModal(`<h2>📋 Le tue prenotazioni</h2>
    <div class="aff-note">Pagamenti e commissione sono <b>simulati</b> in questo prototipo (in produzione: escrow via Stripe, commissione 5% al locale).</div>
    <div id="bkList" style="margin-top:8px">${rows}</div>`);
  bindBookingActions();
}
function bookingRow(bk) {
  const st = STATUS[bk.status] || { t: bk.status, c: "" };
  const fee = bk.quote || bk.budget;
  let action = "";
  if (bk.status === "requested") action = `<div class="loc">In attesa del preventivo della band…</div>`;
  else if (bk.status === "quoted" && bk.kind === "venue") action = `<button class="btn small" data-act="confirm" data-id="${bk.id}">Conferma · acconto 30% (simulato)</button>`;
  else if (bk.status === "quoted" && bk.kind === "band") action = `<div class="loc">In attesa di conferma del locale…</div>`;
  else if (bk.status === "confirmed") action = `<button class="btn small secondary" data-act="complete" data-id="${bk.id}">Segna serata completata</button>`;
  else if (bk.status === "completed") action = `<button class="btn small" data-act="review" data-id="${bk.id}">⭐ Lascia recensione</button>`;
  else if (bk.status === "reviewed") action = reviewsHtml(bk);
  const payline = (bk.status === "confirmed" || bk.status === "completed" || bk.status === "reviewed")
    ? `<div class="loc" style="margin-top:4px">💶 ${esc(fee)} · commissione JamMate 5% (al locale) · acconto in escrow (simulato)</div>` : "";
  return `<div class="card flat" style="margin-bottom:10px">
    <div class="row-between"><b>${esc(bk.bandName)} ↔ ${esc(bk.venueName)}</b><span class="tag ${st.c === "ok" ? "lvl" : st.c === "accent" ? "accent" : ""}">${st.t}</span></div>
    <div class="loc" style="margin-top:4px">📅 ${formatDate(bk.date)} · 💶 ${esc(fee)}</div>
    ${payline}
    <div style="margin-top:10px">${action}</div>
  </div>`;
}
function reviewsHtml(bk) {
  const mine = bk.myReview, other = bk.counterReview;
  return `<div class="aff-note">⭐ <b>La tua recensione:</b> ${"★".repeat(mine.rating)} — ${esc(mine.text || "(nessun commento)")}</div>
    <div class="aff-note" style="margin-top:6px">⭐ <b>Recensione ricevuta:</b> ${"★".repeat(other.rating)} — ${esc(other.text)}</div>`;
}
function bindBookingActions() {
  document.querySelectorAll("[data-act]").forEach(btn => btn.onclick = () => {
    const bk = (state.bookings || []).find(x => x.id === btn.dataset.id); if (!bk) return;
    if (btn.dataset.act === "confirm") { bk.status = "confirmed"; save(); toast("Confermata! Acconto 30% in escrow (simulato) 💳"); openBookings(); }
    else if (btn.dataset.act === "complete") { bk.status = "completed"; save(); toast("Serata completata 🎉 — ora potete recensirvi"); openBookings(); }
    else if (btn.dataset.act === "review") openReviewSheet(bk);
  });
}
function openReviewSheet(bk) {
  // chi recensisco? se ho proposto come band -> recensisco il locale; se sono locale -> la band
  const target = bk.kind === "band" ? bk.venueName : bk.bandName;
  let rating = 5;
  openModal(`<h2>⭐ Recensisci: ${esc(target)}</h2>
    <div class="aff-note">Recensione <b>verificata</b> (solo dopo una serata completata) e a <b>doppio cieco</b>: vedrai la recensione ricevuta solo dopo aver inviato la tua.</div>
    <div class="lk" style="margin-top:12px"><div class="lk-q">Valutazione</div>
      <div class="likert" id="rvStars">${[1, 2, 3, 4, 5].map(v => `<button type="button" data-v="${v}" class="${v === 5 ? "on" : ""}">${v}★</button>`).join("")}</div></div>
    <label class="field" style="margin-top:10px">Commento</label><textarea id="rvText" placeholder="Puntualità, professionalità, intesa…"></textarea>
    <button class="btn" id="rvSend" style="margin-top:14px">Invia recensione</button>`);
  document.querySelectorAll("#rvStars button").forEach(b => b.onclick = () => { document.querySelectorAll("#rvStars button").forEach(x => x.classList.remove("on")); b.classList.add("on"); rating = +b.dataset.v; });
  $("#rvSend").onclick = () => {
    bk.myReview = { rating, text: $("#rvText").value.trim() };
    // recensione "ricevuta" simulata (rivelazione simultanea)
    const canned = bk.kind === "band"
      ? ["Band puntuale e coinvolgente, ottima intesa con il pubblico.", "Professionali, suono pulito. Li richiameremo."]
      : ["Locale organizzato, pagamento puntuale, staff gentile.", "Bel palco e pubblico caloroso, esperienza top."];
    bk.counterReview = { rating: 4 + (Math.random() < 0.6 ? 1 : 0), text: canned[Math.floor(Math.random() * canned.length)] };
    bk.status = "reviewed"; save(); toast("Recensione inviata ⭐ — rivelazione reciproca!"); openBookings();
  };
}

window.renderPalco = renderPalco;
