/* /v1 — Lezioni (#12): insegnanti, slot a calendario, prenotazione+pagamento. */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query, tx } = require("../lib/db");

// GET /teachers — insegnanti con n. slot liberi
app.http("teachers-list", {
  methods: ["GET"], authLevel: "anonymous", route: "teachers",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT t.user_id AS id, u.display_name AS name, mp.avatar, mp.color,
              t.instruments, t.bio, t.hourly_cents AS "hourlyCents", t.city, t.online,
              (SELECT count(*)::int FROM lesson_slots s WHERE s.teacher_id=t.user_id AND NOT s.is_booked AND s.starts_at >= now()) AS "freeSlots"
         FROM teacher_profiles t
         JOIN users u ON u.id=t.user_id
         LEFT JOIN musician_profiles mp ON mp.user_id=t.user_id
        ORDER BY "freeSlots" DESC LIMIT 50`);
    return json(200, rows);
  })
});

// GET /teachers/{id}/slots — slot liberi di un insegnante
app.http("teacher-slots", {
  methods: ["GET"], authLevel: "anonymous", route: "teachers/{id}/slots",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT id, starts_at AS "startsAt", duration_min AS "durationMin"
         FROM lesson_slots WHERE teacher_id=$1 AND NOT is_booked AND starts_at >= now()
        ORDER BY starts_at`, [req.params.id]);
    return json(200, rows);
  })
});

// PUT /teacher — crea/aggiorna il MIO profilo insegnante
app.http("teacher-upsert", {
  methods: ["PUT"], authLevel: "anonymous", route: "teacher",
  handler: withAuth(async (req, ctx, user) => {
    const b = await req.json();
    if (!b.instruments || !b.instruments.length) return json(400, { error: "strumenti mancanti" });
    await query(
      `INSERT INTO teacher_profiles (user_id, instruments, bio, hourly_cents, city, online)
       VALUES ($1,$2,$3,$4,$5,$6)
       ON CONFLICT (user_id) DO UPDATE SET instruments=$2, bio=$3, hourly_cents=$4, city=$5, online=$6`,
      [user.id, b.instruments, b.bio || null, b.hourlyCents || 3000, b.city || null, !!b.online]);
    return json(200, { ok: true });
  })
});

// POST /teacher/slots — aggiunge uno slot di disponibilità
app.http("teacher-slot-add", {
  methods: ["POST"], authLevel: "anonymous", route: "teacher/slots",
  handler: withAuth(async (req, ctx, user) => {
    const b = await req.json();
    if (!b.startsAt) return json(400, { error: "startsAt mancante" });
    const [row] = await query(
      `INSERT INTO lesson_slots (teacher_id, starts_at, duration_min) VALUES ($1,$2,$3) RETURNING id`,
      [user.id, b.startsAt, b.durationMin || 60]);
    return json(201, { id: row.id });
  })
});

// GET /lesson-bookings — le mie lezioni prenotate (come allievo)
app.http("lesson-bookings-list", {
  methods: ["GET"], authLevel: "anonymous", route: "lesson-bookings",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT lb.id, lb.status, lb.amount_cents AS "amountCents",
              s.starts_at AS "startsAt", u.display_name AS "teacherName", mp.avatar, mp.color
         FROM lesson_bookings lb
         JOIN lesson_slots s ON s.id=lb.slot_id
         JOIN users u ON u.id=s.teacher_id
         LEFT JOIN musician_profiles mp ON mp.user_id=s.teacher_id
        WHERE lb.student_id=$1 ORDER BY s.starts_at DESC`, [user.id]);
    return json(200, rows);
  })
});

// POST /lesson-bookings — prenota uno slot (pagamento gestito poi via Stripe)
app.http("lesson-booking-create", {
  methods: ["POST"], authLevel: "anonymous", route: "lesson-bookings",
  handler: withAuth(async (req, ctx, user) => {
    const { slotId } = await req.json();
    if (!slotId) return json(400, { error: "slotId mancante" });
    return await tx(async (c) => {
      const [slot] = (await c.query(
        `SELECT s.id, s.is_booked, t.hourly_cents FROM lesson_slots s
           JOIN teacher_profiles t ON t.user_id=s.teacher_id WHERE s.id=$1 FOR UPDATE`, [slotId])).rows;
      if (!slot) return json(404, { error: "slot non trovato" });
      if (slot.is_booked) return json(409, { error: "slot già prenotato" });
      const amount = slot.hourly_cents, fee = Math.round(amount * 0.1);
      await c.query(`UPDATE lesson_slots SET is_booked=true WHERE id=$1`, [slotId]);
      const [bk] = (await c.query(
        `INSERT INTO lesson_bookings (slot_id, student_id, status, amount_cents, fee_cents)
         VALUES ($1,$2,'confirmed',$3,$4) RETURNING id`, [slotId, user.id, amount, fee])).rows;
      // TODO (Tappa 6): creare PaymentIntent Stripe e passare status 'pending_payment' → 'confirmed' al webhook.
      return json(201, { id: bk.id, amountCents: amount });
    });
  })
});
