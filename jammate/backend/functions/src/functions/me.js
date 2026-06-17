/* /v1/me — profilo dell'utente autenticato (GET/PUT/DELETE). Vedi openapi.yaml. */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query } = require("../lib/db");

// GET /me — profilo completo (musicista + deep + reputazione)
app.http("me-get", {
  methods: ["GET"], authLevel: "anonymous", route: "me",
  handler: withAuth(async (request, context, user) => {
    const [profile] = await query(
      `SELECT avatar, photo_url AS "photoUrl", color, city, level, bio, tagline,
              instruments, genres, links
         FROM musician_profiles WHERE user_id = $1`, [user.id]);
    const [deep] = await query(
      `SELECT done, values, big5, ipc, goal FROM deep_profiles WHERE user_id = $1`, [user.id]);
    return json(200, { id: user.id, email: user.email, profile: profile || null, deep: deep || { done: false } });
  })
});

// PUT /me — crea/aggiorna il profilo musicista (upsert)
app.http("me-put", {
  methods: ["PUT"], authLevel: "anonymous", route: "me",
  handler: withAuth(async (request, context, user) => {
    const b = await request.json();
    await query(
      `INSERT INTO musician_profiles
         (user_id, avatar, photo_url, color, city, level, bio, tagline, instruments, genres, links, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11, now())
       ON CONFLICT (user_id) DO UPDATE SET
         avatar=$2, photo_url=$3, color=$4, city=$5, level=$6, bio=$7, tagline=$8,
         instruments=$9, genres=$10, links=$11, updated_at=now()`,
      [user.id, b.avatar, b.photoUrl, b.color, b.city, b.level, b.bio, b.tagline,
       b.instruments || [], b.genres || [], b.links || {}]);
    return json(200, { ok: true });
  })
});

// DELETE /me — GDPR: cancellazione account e dati (soft-delete + CASCADE)
app.http("me-delete", {
  methods: ["DELETE"], authLevel: "anonymous", route: "me",
  handler: withAuth(async (request, context, user) => {
    // TODO (Tappa 6/8): cancellare anche i media su Blob Storage prima del delete.
    await query("DELETE FROM users WHERE id = $1", [user.id]); // CASCADE pulisce le tabelle collegate
    return { status: 204 };
  })
});
