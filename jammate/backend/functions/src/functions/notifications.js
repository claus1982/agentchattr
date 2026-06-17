/* /v1/notifications — centro notifiche (#10). La generazione lato server avverrà
 * dagli eventi (match, inviti, jam, prenotazioni…); la realtime via Web PubSub (ADR 0007). */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query } = require("../lib/db");

// GET /notifications — le mie notifiche (recenti prima)
app.http("notifications-list", {
  methods: ["GET"], authLevel: "anonymous", route: "notifications",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT id, icon, text, link_view AS view, read, created_at AS ts
         FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50`, [user.id]);
    return json(200, rows);
  })
});

// PATCH /notifications/read — segna tutte come lette
app.http("notifications-read", {
  methods: ["PATCH"], authLevel: "anonymous", route: "notifications/read",
  handler: withAuth(async (req, ctx, user) => {
    await query(`UPDATE notifications SET read=true WHERE user_id=$1 AND NOT read`, [user.id]);
    return json(200, { ok: true });
  })
});

// DELETE /notifications — pulisce tutte le mie notifiche
app.http("notifications-clear", {
  methods: ["DELETE"], authLevel: "anonymous", route: "notifications",
  handler: withAuth(async (req, ctx, user) => {
    await query(`DELETE FROM notifications WHERE user_id=$1`, [user.id]);
    return { status: 204 };
  })
});
