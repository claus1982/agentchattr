/* /v1/venues — locali e serate aperte (open nights). */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query } = require("../lib/db");

const venueCols = `v.id, v.name, v.avatar, v.color, v.type, v.city, v.capacity, v.genres, v.rating, v.ratings`;

// GET /venues — locali (con la prossima serata aperta, se presente)
app.http("venues-list", {
  methods: ["GET"], authLevel: "anonymous", route: "venues",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT ${venueCols},
              (SELECT to_jsonb(o) FROM (
                 SELECT night_date AS date, genre, budget FROM open_nights
                  WHERE venue_id=v.id AND night_date >= current_date
                  ORDER BY night_date LIMIT 1) o) AS "openNight"
         FROM venues v ORDER BY v.rating DESC LIMIT 50`);
    return json(200, rows);
  })
});

// GET /venues/mine — i miei locali
app.http("venues-mine", {
  methods: ["GET"], authLevel: "anonymous", route: "venues/mine",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(`SELECT ${venueCols} FROM venues v WHERE v.owner_id=$1 ORDER BY v.created_at DESC`, [user.id]);
    return json(200, rows);
  })
});

// POST /venues — crea un profilo locale
app.http("venues-create", {
  methods: ["POST"], authLevel: "anonymous", route: "venues",
  handler: withAuth(async (req, ctx, user) => {
    const b = await req.json();
    if (!b.name) return json(400, { error: "nome mancante" });
    const [row] = await query(
      `INSERT INTO venues (owner_id, name, avatar, color, type, city, capacity, genres)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id`,
      [user.id, b.name, b.avatar || "🏢", b.color, b.type, b.city, b.capacity || null, b.genres || []]);
    return json(201, { id: row.id });
  })
});

// PUT /venues/{id} — aggiorna (solo proprietario)
app.http("venues-update", {
  methods: ["PUT"], authLevel: "anonymous", route: "venues/{id}",
  handler: withAuth(async (req, ctx, user) => {
    const id = req.params.id, b = await req.json();
    const own = await query(`SELECT 1 FROM venues WHERE id=$1 AND owner_id=$2`, [id, user.id]);
    if (!own.length) return json(403, { error: "non sei il proprietario" });
    await query(
      `UPDATE venues SET name=COALESCE($2,name), type=$3, city=$4, capacity=$5, genres=COALESCE($6,genres) WHERE id=$1`,
      [id, b.name, b.type, b.city, b.capacity || null, b.genres]);
    return json(200, { ok: true });
  })
});

// POST /venues/{id}/nights — pubblica una serata aperta
app.http("venue-night-create", {
  methods: ["POST"], authLevel: "anonymous", route: "venues/{id}/nights",
  handler: withAuth(async (req, ctx, user) => {
    const id = req.params.id, b = await req.json();
    const own = await query(`SELECT 1 FROM venues WHERE id=$1 AND owner_id=$2`, [id, user.id]);
    if (!own.length) return json(403, { error: "non sei il proprietario" });
    if (!b.date) return json(400, { error: "data mancante" });
    const [row] = await query(
      `INSERT INTO open_nights (venue_id, night_date, genre, budget) VALUES ($1,$2,$3,$4) RETURNING id`,
      [id, b.date, b.genre || null, b.budget || null]);
    return json(201, { id: row.id });
  })
});
