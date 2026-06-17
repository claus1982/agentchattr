/* /v1 — estensioni del profilo: repertorio, Profilo Profondo, endorsement. */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query } = require("../lib/db");

// GET /repertoire — i brani con tonalità dell'utente
app.http("repertoire-list", {
  methods: ["GET"], authLevel: "anonymous", route: "repertoire",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT id, song AS title, artist, song_key AS key FROM repertoire WHERE user_id=$1 ORDER BY id`, [user.id]);
    return json(200, rows);
  })
});

// POST /repertoire — aggiunge un brano
app.http("repertoire-add", {
  methods: ["POST"], authLevel: "anonymous", route: "repertoire",
  handler: withAuth(async (req, ctx, user) => {
    const b = await req.json();
    if (!b.title) return json(400, { error: "titolo mancante" });
    const [row] = await query(
      `INSERT INTO repertoire (user_id, song, artist, song_key) VALUES ($1,$2,$3,$4)
       RETURNING id, song AS title, artist, song_key AS key`,
      [user.id, b.title, b.artist || null, b.key || null]);
    return json(201, row);
  })
});

// DELETE /repertoire/{id}
app.http("repertoire-del", {
  methods: ["DELETE"], authLevel: "anonymous", route: "repertoire/{id}",
  handler: withAuth(async (req, ctx, user) => {
    await query(`DELETE FROM repertoire WHERE id=$1 AND user_id=$2`, [req.params.id, user.id]);
    return { status: 204 };
  })
});

// PUT /deep — salva i risultati del Profilo Profondo (upsert)
app.http("deep-put", {
  methods: ["PUT"], authLevel: "anonymous", route: "deep",
  handler: withAuth(async (req, ctx, user) => {
    const b = await req.json();
    await query(
      `INSERT INTO deep_profiles (user_id, done, values, big5, ipc, goal, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6, now())
       ON CONFLICT (user_id) DO UPDATE SET
         done=$2, values=$3, big5=$4, ipc=$5, goal=$6, updated_at=now()`,
      [user.id, b.done !== false, b.values || {}, b.big5 || {}, b.ipc || {}, b.goal || {}]);
    return json(200, { ok: true });
  })
});

// POST /endorsements — lascia un endorsement post-jam a un altro utente
app.http("endorsement-add", {
  methods: ["POST"], authLevel: "anonymous", route: "endorsements",
  handler: withAuth(async (req, ctx, user) => {
    const b = await req.json();
    if (!b.targetUserId) return json(400, { error: "targetUserId mancante" });
    if (b.targetUserId === user.id) return json(400, { error: "non puoi endorsare te stesso" });
    const [row] = await query(
      `INSERT INTO endorsements (target_user, author_user, puntualita, tecnica, attitudine)
       VALUES ($1,$2,$3,$4,$5)
       ON CONFLICT (target_user, author_user) DO UPDATE SET
         puntualita=$3, tecnica=$4, attitudine=$5, created_at=now()
       RETURNING id`,
      [b.targetUserId, user.id, b.puntualita ?? 5, b.tecnica ?? 5, b.attitudine ?? 5]);
    return json(201, { id: row.id });
  })
});

// GET /endorsements/{userId}/summary — medie reputazione di un profilo
app.http("endorsement-summary", {
  methods: ["GET"], authLevel: "anonymous", route: "endorsements/{userId}/summary",
  handler: withAuth(async (req, ctx, user) => {
    const [row] = await query(
      `SELECT count(*)::int AS endorsements,
              COALESCE(round(avg(puntualita)*20),0)::int AS puntualita,
              COALESCE(round(avg(tecnica)*20),0)::int    AS tecnica,
              COALESCE(round(avg(attitudine)*20),0)::int AS attitudine
         FROM endorsements WHERE target_user=$1`, [req.params.userId]);
    return json(200, row);
  })
});
