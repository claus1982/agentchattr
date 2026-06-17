/* /v1/bands — bande, formazione e inviti (#6). */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query, tx } = require("../lib/db");

const bandCols = `b.id, b.name, b.avatar, b.color, b.city, b.fee, b.tagline,
                  b.genres, b.available, b.rating, b.ratings`;

// GET /bands — bande disponibili (per i locali)
app.http("bands-list", {
  methods: ["GET"], authLevel: "anonymous", route: "bands",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(`SELECT ${bandCols} FROM bands b WHERE b.available ORDER BY b.rating DESC LIMIT 50`);
    return json(200, rows);
  })
});

// GET /bands/mine — le bande di cui sono membro/admin
app.http("bands-mine", {
  methods: ["GET"], authLevel: "anonymous", route: "bands/mine",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT ${bandCols}, bm.is_admin AS "isAdmin"
         FROM bands b JOIN band_members bm ON bm.band_id=b.id
        WHERE bm.user_id=$1 ORDER BY b.created_at DESC`, [user.id]);
    return json(200, rows);
  })
});

// POST /bands — crea una band (il creatore ne è admin)
app.http("bands-create", {
  methods: ["POST"], authLevel: "anonymous", route: "bands",
  handler: withAuth(async (req, ctx, user) => {
    const b = await req.json();
    if (!b.name) return json(400, { error: "nome mancante" });
    return await tx(async (c) => {
      const [band] = (await c.query(
        `INSERT INTO bands (name, avatar, color, city, fee, tagline, genres, available)
         VALUES ($1,$2,$3,$4,$5,$6,$7, COALESCE($8,true)) RETURNING id`,
        [b.name, b.avatar || "🎸", b.color, b.city, b.fee, b.tagline, b.genres || [], b.available])).rows;
      await c.query(
        `INSERT INTO band_members (band_id, user_id, role, is_admin) VALUES ($1,$2,$3,true)`,
        [band.id, user.id, (b.role || null)]);
      for (const song of (b.repertoire || [])) await c.query(
        `INSERT INTO band_repertoire (band_id, song) VALUES ($1,$2)`, [band.id, song]);
      return json(201, { id: band.id });
    });
  })
});

// PUT /bands/{id} — aggiorna (solo admin)
app.http("bands-update", {
  methods: ["PUT"], authLevel: "anonymous", route: "bands/{id}",
  handler: withAuth(async (req, ctx, user) => {
    const id = req.params.id, b = await req.json();
    const admin = await query(`SELECT 1 FROM band_members WHERE band_id=$1 AND user_id=$2 AND is_admin`, [id, user.id]);
    if (!admin.length) return json(403, { error: "non sei admin di questa band" });
    await query(
      `UPDATE bands SET name=COALESCE($2,name), fee=$3, tagline=$4, city=$5,
              genres=COALESCE($6,genres), available=COALESCE($7,available) WHERE id=$1`,
      [id, b.name, b.fee, b.tagline, b.city, b.genres, b.available]);
    return json(200, { ok: true });
  })
});

// POST /bands/{id}/invites — invita un musicista
app.http("band-invite-create", {
  methods: ["POST"], authLevel: "anonymous", route: "bands/{id}/invites",
  handler: withAuth(async (req, ctx, user) => {
    const bandId = req.params.id, b = await req.json();
    const admin = await query(`SELECT 1 FROM band_members WHERE band_id=$1 AND user_id=$2 AND is_admin`, [bandId, user.id]);
    if (!admin.length) return json(403, { error: "non sei admin di questa band" });
    if (!b.inviteeId) return json(400, { error: "inviteeId mancante" });
    const [row] = await query(
      `INSERT INTO band_invites (band_id, invitee_id, inviter_id, role, message)
       VALUES ($1,$2,$3,$4,$5)
       ON CONFLICT (band_id, invitee_id) DO UPDATE SET role=$4, message=$5, status='pending', created_at=now()
       RETURNING id, status`,
      [bandId, b.inviteeId, user.id, b.role || null, b.message || null]);
    return json(201, row);
  })
});

// GET /invites — i miei inviti ricevuti (in attesa)
app.http("band-invites-mine", {
  methods: ["GET"], authLevel: "anonymous", route: "invites",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT i.id, i.band_id AS "bandId", b.name AS "bandName", b.avatar, b.color,
              i.role, i.message, i.status, i.created_at AS "createdAt"
         FROM band_invites i JOIN bands b ON b.id=i.band_id
        WHERE i.invitee_id=$1 AND i.status='pending' ORDER BY i.created_at DESC`, [user.id]);
    return json(200, rows);
  })
});

// PATCH /invites/{id} — accetta/rifiuta un invito; se accettato entra in formazione
app.http("band-invite-respond", {
  methods: ["PATCH"], authLevel: "anonymous", route: "invites/{id}",
  handler: withAuth(async (req, ctx, user) => {
    const id = req.params.id, { action } = await req.json();
    if (!["accept", "decline"].includes(action)) return json(400, { error: "action non valida" });
    return await tx(async (c) => {
      const [inv] = (await c.query(
        `SELECT band_id, role FROM band_invites WHERE id=$1 AND invitee_id=$2 AND status='pending'`,
        [id, user.id])).rows;
      if (!inv) return json(404, { error: "invito non trovato" });
      const status = action === "accept" ? "accepted" : "declined";
      await c.query(`UPDATE band_invites SET status=$2, responded_at=now() WHERE id=$1`, [id, status]);
      if (action === "accept") await c.query(
        `INSERT INTO band_members (band_id, user_id, role) VALUES ($1,$2,$3)
         ON CONFLICT (band_id, user_id) DO NOTHING`, [inv.band_id, user.id, inv.role]);
      return json(200, { status });
    });
  })
});
