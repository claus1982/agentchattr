/* GET /v1/discover — profili consigliati con punteggio di affinità.
 * Riusa il motore di matching del frontend (affinity.js) lato server. */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query } = require("../lib/db");

app.http("discover", {
  methods: ["GET"], authLevel: "anonymous", route: "discover",
  handler: withAuth(async (request, context, user) => {
    const q = request.query;
    const instrument = q.get("instrument") || null;
    const level = q.get("level") || null;
    const genre = q.get("genre") || null;

    // Candidati: profili diversi dal mio, non ancora swipati, filtrati.
    const rows = await query(
      `SELECT u.id, p.avatar, p.photo_url AS "photoUrl", p.city, p.distance_km AS "distanceKm",
              p.level, p.instruments, p.genres, p.tagline
         FROM musician_profiles p
         JOIN users u ON u.id = p.user_id
        WHERE u.id <> $1
          AND u.deleted_at IS NULL
          AND u.id NOT IN (SELECT target_user FROM swipes WHERE user_id = $1)
          AND ($2::text IS NULL OR $2 = ANY(p.instruments))
          AND ($3::text IS NULL OR p.level = $3)
          AND ($4::text IS NULL OR $4 = ANY(p.genres))
        LIMIT 50`,
      [user.id, instrument, level, genre]);

    // TODO (Tappa 4): calcolare l'affinità con il motore condiviso (affinity.js)
    // usando i deep_profiles di user e candidato, e ordinare per punteggio.
    // Placeholder: nessun punteggio finché il motore non è collegato server-side.
    return json(200, rows.map(r => ({ ...r, affinity: null })));
  })
});
