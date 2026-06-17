/* /v1 — match e messaggi diretti (DM). */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query, tx } = require("../lib/db");

// GET /matches — i miei contatti (controparti) con ultimo messaggio
app.http("matches-list", {
  methods: ["GET"], authLevel: "anonymous", route: "matches",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `WITH peers AS (
         SELECT CASE WHEN m.user_a=$1 THEN m.user_b ELSE m.user_a END AS peer
           FROM matches m WHERE m.user_a=$1 OR m.user_b=$1)
       SELECT p.peer AS "userId", u.display_name AS name, mp.avatar, mp.color, mp.city,
              (SELECT body FROM messages msg
                 JOIN thread_participants ta ON ta.thread_id=msg.thread_id AND ta.user_id=$1
                 JOIN thread_participants tb ON tb.thread_id=msg.thread_id AND tb.user_id=p.peer
                ORDER BY msg.created_at DESC LIMIT 1) AS "lastMessage"
         FROM peers p JOIN users u ON u.id=p.peer
         LEFT JOIN musician_profiles mp ON mp.user_id=p.peer`, [user.id]);
    return json(200, rows);
  })
});

// Trova o crea il thread DM fra due utenti.
async function dmThread(c, a, b) {
  const found = (await c.query(
    `SELECT t.id FROM threads t
       JOIN thread_participants ta ON ta.thread_id=t.id AND ta.user_id=$1
       JOIN thread_participants tb ON tb.thread_id=t.id AND tb.user_id=$2
      WHERE t.kind='dm' LIMIT 1`, [a, b])).rows[0];
  if (found) return found.id;
  const t = (await c.query(`INSERT INTO threads (kind) VALUES ('dm') RETURNING id`)).rows[0];
  await c.query(`INSERT INTO thread_participants (thread_id, user_id) VALUES ($1,$2),($1,$3)`, [t.id, a, b]);
  return t.id;
}

// GET /messages/{userId} — conversazione con un utente
app.http("messages-get", {
  methods: ["GET"], authLevel: "anonymous", route: "messages/{userId}",
  handler: withAuth(async (req, ctx, user) => {
    const peer = req.params.userId;
    const rows = await tx(async (c) => {
      const tid = await dmThread(c, user.id, peer);
      return (await c.query(
        `SELECT (sender_id=$2) AS mine, body AS text, created_at AS ts
           FROM messages WHERE thread_id=$1 ORDER BY created_at`, [tid, user.id])).rows;
    });
    return json(200, rows);
  })
});

// POST /messages/{userId} — invia un messaggio
app.http("messages-send", {
  methods: ["POST"], authLevel: "anonymous", route: "messages/{userId}",
  handler: withAuth(async (req, ctx, user) => {
    const peer = req.params.userId, { text } = await req.json();
    if (!text) return json(400, { error: "testo mancante" });
    const out = await tx(async (c) => {
      const tid = await dmThread(c, user.id, peer);
      const [row] = (await c.query(
        `INSERT INTO messages (thread_id, sender_id, body) VALUES ($1,$2,$3) RETURNING id, created_at AS ts`,
        [tid, user.id, text])).rows;
      return row;
    });
    return json(201, out);
  })
});
