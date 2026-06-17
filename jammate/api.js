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

    // --- Profilo (vedi openapi.yaml: /me, /me/deep, /me/photo) ---
    me: {
      get:    () => get("/me"),
      update: (profile) => put("/me", profile),
      remove: () => del("/me"),                 // GDPR: cancella account
      saveDeep: (deep) => put("/me/deep", deep),
      uploadPhoto: (file) => {                  // file: File/Blob
        const fd = new FormData(); fd.append("file", file);
        return post("/me/photo", fd, { isForm: true });
      }
    },

    // --- Scoperta / match ---
    discover: (filters) => get("/discover", { query: filters }),
    swipe:    (targetUserId, decision) => post("/swipes", { targetUserId, decision }),
    matches:  () => get("/matches"),

    // --- Band ---
    bands: {
      mine:   () => get("/bands"),
      create: (band) => post("/bands", band),
      update: (id, band) => put(`/bands/${id}`, band)
    },

    // --- Locali ---
    venues: {
      list:   (city) => get("/venues", { query: { city } }),
      create: (venue) => post("/venues", venue)
    },

    // --- Prenotazioni ---
    bookings: {
      list:    () => get("/bookings"),
      create:  (booking) => post("/bookings", booking),
      setStatus: (id, status, quote) => patch(`/bookings/${id}/status`, { status, quote }),
      review:  (id, rating, text) => post(`/bookings/${id}/reviews`, { rating, text })
    },

    // --- Chat ---
    threads: {
      messages: (id) => get(`/threads/${id}/messages`),
      send:     (id, bodyText) => post(`/threads/${id}/messages`, { body: bodyText })
    },

    // --- Diagnostica ---
    health: () => get("/health")
  };
})();
