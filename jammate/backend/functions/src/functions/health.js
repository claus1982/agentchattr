/* GET /v1/health — verifica vita servizio + connessione DB. Nessuna auth. */
"use strict";
const { app } = require("@azure/functions");
const { json, safe } = require("../lib/http");
const { query } = require("../lib/db");

app.http("health", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "health",
  handler: safe(async () => {
    let db = "down";
    try { await query("SELECT 1"); db = "up"; } catch (_) { /* db down */ }
    return json(200, { status: "ok", db, time: new Date().toISOString() });
  })
});
