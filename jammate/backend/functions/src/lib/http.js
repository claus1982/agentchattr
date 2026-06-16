/* Helper HTTP: risposte JSON coerenti e gestione errori centralizzata. */
"use strict";
const { getCurrentUser, HttpError } = require("./auth");

function json(status, body) {
  return { status, jsonBody: body };
}

/** Avvolge un handler: inietta l'utente autenticato e converte gli errori in risposte pulite. */
function withAuth(handler) {
  return async (request, context) => {
    try {
      const user = await getCurrentUser(request);
      return await handler(request, context, user);
    } catch (e) {
      if (e instanceof HttpError) return json(e.status, { error: e.message });
      context.error(e);
      return json(500, { error: "Errore interno" });
    }
  };
}

/** Variante senza autenticazione (es. health, webhook con firma propria). */
function safe(handler) {
  return async (request, context) => {
    try { return await handler(request, context); }
    catch (e) {
      if (e instanceof HttpError) return json(e.status, { error: e.message });
      context.error(e);
      return json(500, { error: "Errore interno" });
    }
  };
}

module.exports = { json, withAuth, safe };
