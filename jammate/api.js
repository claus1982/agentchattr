/* JamMate — Client API (data layer "api").
 *
 * È il pezzo che collega la PWA al backend Azure Functions definito in
 * backend/openapi.yaml. Oggi NON è ancora attivo: l'app usa il backend locale
 * (storage.js). Al Passo 8 del deploy lo configuriamo e iniziamo a migrare i
 * flussi uno per uno (vedi ADR 0005).
 *
 * Uso (dopo il deploy):
 *   JM.Api.configure({
 *     baseUrl: "https://jammate-api-XXX.azurewebsites.net/v1",
 *     getToken: async () => msalToken   // token di Microsoft Entra External ID
 *   });
 *   const me = await JM.Api.me.get();
 *
 * Nessuna dipendenza esterna: solo fetch. Stile coerente col resto dell'app.
 */
(function () {
  "use strict";
  window.JM = window.JM || {};

  const cfg = {
    baseUrl: "",
    // Fornitore del token Bearer (Entra). Sovrascritto da configure().
    getToken: async () => null
  };

  class ApiError extends Error {
    constructor(status, message, body) {
      super(message || `Errore API ${status}`);
      this.status = status;
      this.body = body;
    }
  }

  /* Richiesta generica. Aggiunge il token, gestisce JSON ed errori in modo uniforme. */
  async function request(method, path, { body, query, isForm } = {}) {
    if (!cfg.baseUrl) throw new ApiError(0, "JM.Api non configurato (manca baseUrl)");

    let url = cfg.baseUrl.replace(/\/$/, "") + path;
    if (query) {
      const qs = new URLSearchParams(
        Object.entries(query).filter(([, v]) => v != null && v !== "")
      ).toString();
      if (qs) url += "?" + qs;
    }

    const headers = {};
    const token = await cfg.getToken();
    if (token) headers["Authorization"] = "Bearer " + token;

    const init = { method, headers };
    if (body != null) {
      if (isForm) { init.body = body; }            // FormData (es. upload foto): niente Content-Type manuale
      else { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    }

    const res = await fetch(url, init);
    if (res.status === 204) return null;

    let data = null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) { try { data = await res.json(); } catch (_) { /* ignore */ } }

    if (!res.ok) throw new ApiError(res.status, data && data.error, data);
    return data;
  }

  const get  = (p, opts)        => request("GET", p, opts);
  const post = (p, body, opts)  => request("POST", p, { ...opts, body });
  const put  = (p, body)        => request("PUT", p, { body });
  const patch = (p, body)       => request("PATCH", p, { body });
  const del  = (p)              => request("DELETE", p);

  JM.Api = {
    ApiError,
    configure(options) { Object.assign(cfg, options); },
    get baseUrl() { return cfg.baseUrl; },

    // --- Profilo ---
    me: {
      get:      () => get("/me"),
      update:   (profile) => put("/me", profile),
      remove:   () => del("/me"),               // GDPR: cancella account
      saveDeep: (deep) => put("/deep", deep)
    },
    // --- Repertorio ---
    repertoire: {
      list:   () => get("/repertoire"),
      add:    (song) => post("/repertoire", song),
      remove: (id) => del(`/repertoire/${id}`)
    },
    // --- Reputazione ---
    endorsements: {
      add:     (targetUserId, scores) => post("/endorsements", { targetUserId, ...scores }),
      summary: (userId) => get(`/endorsements/${userId}/summary`)
    },

    // --- Scoperta / match / messaggi ---
    discover: (filters) => get("/discover", { query: filters }),
    swipe:    (targetUserId, decision) => post("/swipes", { targetUserId, decision }),
    matches:  () => get("/matches"),
    messages: {
      with: (userId) => get(`/messages/${userId}`),
      send: (userId, text) => post(`/messages/${userId}`, { text })
    },

    // --- Band + inviti ---
    bands: {
      list:    () => get("/bands"),
      mine:    () => get("/bands/mine"),
      create:  (band) => post("/bands", band),
      update:  (id, band) => put(`/bands/${id}`, band),
      invite:  (id, inviteeId, role, message) => post(`/bands/${id}/invites`, { inviteeId, role, message }),
      myInvites: () => get("/invites"),
      respondInvite: (inviteId, action) => patch(`/invites/${inviteId}`, { action })
    },

    // --- Locali + serate ---
    venues: {
      list:     (city) => get("/venues", { query: { city } }),
      mine:     () => get("/venues/mine"),
      create:   (venue) => post("/venues", venue),
      update:   (id, venue) => put(`/venues/${id}`, venue),
      addNight: (id, night) => post(`/venues/${id}/nights`, night)
    },

    // --- Prenotazioni serate ---
    bookings: {
      list:      () => get("/bookings"),
      create:    (booking) => post("/bookings", booking),
      setStatus: (id, status, quote) => patch(`/bookings/${id}/status`, { status, quote })
    },

    // --- Mappa jam ---
    jams: {
      list:     () => get("/jams"),
      create:   (jam) => post("/jams", jam),
      join:     (id) => post(`/jams/${id}/join`),
      leave:    (id) => del(`/jams/${id}/join`),
      requests: (id) => get(`/jams/${id}/requests`),
      decide:   (id, userId, action) => patch(`/jams/${id}/participants/${userId}`, { action })
    },

    // --- Feed ---
    posts: {
      list:    () => get("/posts"),
      create:  (p) => post("/posts", p),
      react:   (id, emoji) => put(`/posts/${id}/reaction`, { emoji }),
      comments: (id) => get(`/posts/${id}/comments`),
      comment: (id, text) => post(`/posts/${id}/comments`, { text })
    },

    // --- Lezioni ---
    lessons: {
      teachers:    () => get("/teachers"),
      teacherSlots: (id) => get(`/teachers/${id}/slots`),
      saveTeacher: (teacher) => put("/teacher", teacher),
      addSlot:     (slot) => post("/teacher/slots", slot),
      myBookings:  () => get("/lesson-bookings"),
      book:        (slotId) => post("/lesson-bookings", { slotId })
    },

    // --- Notifiche ---
    notifications: {
      list:     () => get("/notifications"),
      markRead: () => patch("/notifications/read", {}),
      clear:    () => del("/notifications")
    },

    // --- Diagnostica ---
    health: () => get("/health")
  };
})();
