/* /v1/bookings — marketplace band <-> locale. Stati allineati a gigs.js:
 * requested -> quoted -> confirmed -> completed -> reviewed (+ cancelled). */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query } = require("../lib/db");

// GET /bookings — prenotazioni in cui sono coinvolto (come membro band o titolare locale)
app.http("bookings-list", {
  methods: ["GET"], authLevel: "anonymous", route: "bookings",
  handler: withAuth(async (request, context, user) => {
    const rows = await query(
      `SELECT bk.id, bk.kind, bk.band_id AS "bandId", b.name AS "bandName",
              bk.venue_id AS "venueId", v.name AS "venueName",
              bk.gig_date AS "date", bk.budget, bk.quote, bk.status
         FROM bookings bk
         LEFT JOIN bands  b ON b.id = bk.band_id
         LEFT JOIN venues v ON v.id = bk.venue_id
        WHERE bk.band_id IN (SELECT band_id FROM band_members WHERE user_id = $1)
           OR bk.venue_id IN (SELECT id FROM venues WHERE owner_id = $1)
        ORDER BY bk.gig_date DESC`, [user.id]);
    return json(200, rows);
  })
});

// POST /bookings — crea una richiesta/preventivo
app.http("bookings-create", {
  methods: ["POST"], authLevel: "anonymous", route: "bookings",
  handler: withAuth(async (request, context, user) => {
    const b = await request.json();
    // TODO (Tappa 5): verificare che l'utente sia admin della band o titolare del locale.
    const [row] = await query(
      `INSERT INTO bookings (kind, band_id, venue_id, gig_date, budget, quote, status)
       VALUES ($1,$2,$3,$4,$5,$6,$7)
       RETURNING id, kind, band_id AS "bandId", venue_id AS "venueId",
                 gig_date AS "date", budget, quote, status`,
      [b.kind, b.bandId, b.venueId, b.date, b.budget, b.quote, b.status || "requested"]);
    return json(201, row);
  })
});

// PATCH /bookings/{id}/status — avanza lo stato
app.http("bookings-status", {
  methods: ["PATCH"], authLevel: "anonymous", route: "bookings/{id}/status",
  handler: withAuth(async (request, context, user) => {
    const id = request.params.id;
    const { status, quote } = await request.json();
    const allowed = ["quoted", "confirmed", "completed", "cancelled"];
    if (!allowed.includes(status)) return json(400, { error: "stato non valido" });
    // TODO (Tappa 5/6): controllo autorizzazione per-oggetto + (se confirmed) escrow Stripe.
    await query(
      `UPDATE bookings SET status = $2, quote = COALESCE($3, quote), updated_at = now() WHERE id = $1`,
      [id, status, quote || null]);
    return json(200, { ok: true });
  })
});
