/* /v1/jams — jam geolocalizzate (#9). Accesso ibrido: open | approval. */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query, tx } = require("../lib/db");

// GET /jams — jam future con stato della mia partecipazione e n. partecipanti
app.http("jams-list", {
  methods: ["GET"], authLevel: "anonymous", route: "jams",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT j.id, j.title, j.starts_at AS "startsAt", j.lat, j.lng, j.place,
              j.genres, j.instruments, j.min_level AS "minLevel", j.access_mode AS "accessMode",
              j.host_id AS "hostId", u.display_name AS "hostName", mp.avatar, mp.color,
              (SELECT count(*)::int FROM jam_participants WHERE jam_id=j.id AND status='joined') AS "participants",
              (SELECT status FROM jam_participants WHERE jam_id=j.id AND user_id=$1) AS "myStatus"
         FROM jams j
         JOIN users u ON u.id=j.host_id
         LEFT JOIN musician_profiles mp ON mp.user_id=u.id
        WHERE j.starts_at >= now() - interval '1 day'
        ORDER BY j.starts_at LIMIT 100`, [user.id]);
    return json(200, rows);
  })
});

// POST /jams — crea una jam (l'host vi partecipa)
app.http("jams-create", {
  methods: ["POST"], authLevel: "anonymous", route: "jams",
  handler: withAuth(async (req, ctx, user) => {
    const b = await req.json();
    if (!b.title || !b.startsAt) return json(400, { error: "title/startsAt mancanti" });
    const access = b.accessMode === "approval" ? "approval" : "open";
    return await tx(async (c) => {
      const [j] = (await c.query(
        `INSERT INTO jams (host_id, title, starts_at, lat, lng, place, genres, instruments, min_level, access_mode)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id`,
        [user.id, b.title, b.startsAt, b.lat ?? null, b.lng ?? null, b.place || null,
         b.genres || [], b.instruments || [], b.minLevel ?? 0, access])).rows;
      await c.query(`INSERT INTO jam_participants (jam_id, user_id, status) VALUES ($1,$2,'joined')`, [j.id, user.id]);
      return json(201, { id: j.id });
    });
  })
});

// POST /jams/{id}/join — partecipa (open) o richiedi (approval)
app.http("jams-join", {
  methods: ["POST"], authLevel: "anonymous", route: "jams/{id}/join",
  handler: withAuth(async (req, ctx, user) => {
    const id = req.params.id;
    const [jam] = await query(`SELECT access_mode, host_id FROM jams WHERE id=$1`, [id]);
    if (!jam) return json(404, { error: "jam non trovata" });
    if (jam.host_id === user.id) return json(400, { error: "sei l'host" });
    const status = jam.access_mode === "approval" ? "requested" : "joined";
    await query(
      `INSERT INTO jam_participants (jam_id, user_id, status) VALUES ($1,$2,$3)
       ON CONFLICT (jam_id, user_id) DO UPDATE SET status=$3`, [id, user.id, status]);
    return json(200, { status });
  })
});

// DELETE /jams/{id}/join — annulla partecipazione/richiesta
app.http("jams-leave", {
  methods: ["DELETE"], authLevel: "anonymous", route: "jams/{id}/join",
  handler: withAuth(async (req, ctx, user) => {
    await query(`DELETE FROM jam_participants WHERE jam_id=$1 AND user_id=$2`, [req.params.id, user.id]);
    return { status: 204 };
  })
});

// GET /jams/{id}/requests — richieste da approvare (solo host)
app.http("jams-requests", {
  methods: ["GET"], authLevel: "anonymous", route: "jams/{id}/requests",
  handler: withAuth(async (req, ctx, user) => {
    const id = req.params.id;
    const [jam] = await query(`SELECT host_id FROM jams WHERE id=$1`, [id]);
    if (!jam || jam.host_id !== user.id) return json(403, { error: "solo l'host" });
    const rows = await query(
      `SELECT jp.user_id AS "userId", u.display_name AS name, mp.avatar, mp.color
         FROM jam_participants jp JOIN users u ON u.id=jp.user_id
         LEFT JOIN musician_profiles mp ON mp.user_id=u.id
        WHERE jp.jam_id=$1 AND jp.status='requested'`, [id]);
    return json(200, rows);
  })
});

// PATCH /jams/{id}/participants/{userId} — l'host accetta/rifiuta una richiesta
app.http("jams-decide", {
  methods: ["PATCH"], authLevel: "anonymous", route: "jams/{id}/participants/{userId}",
  handler: withAuth(async (req, ctx, user) => {
    const { id, userId } = req.params, { action } = await req.json();
    const [jam] = await query(`SELECT host_id FROM jams WHERE id=$1`, [id]);
    if (!jam || jam.host_id !== user.id) return json(403, { error: "solo l'host" });
    if (action === "accept") await query(`UPDATE jam_participants SET status='joined' WHERE jam_id=$1 AND user_id=$2`, [id, userId]);
    else await query(`DELETE FROM jam_participants WHERE jam_id=$1 AND user_id=$2`, [id, userId]);
    return json(200, { ok: true });
  })
});
