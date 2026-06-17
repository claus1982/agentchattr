/* POST /v1/swipes — registra like/pass; se reciproco crea un match. */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query, tx } = require("../lib/db");

app.http("swipes", {
  methods: ["POST"], authLevel: "anonymous", route: "swipes",
  handler: withAuth(async (request, context, user) => {
    const { targetUserId, decision } = await request.json();
    if (!targetUserId || !["liked", "passed"].includes(decision))
      return json(400, { error: "targetUserId/decision non validi" });

    return await tx(async (c) => {
      await c.query(
        `INSERT INTO swipes (user_id, target_user, decision) VALUES ($1,$2,$3)
         ON CONFLICT (user_id, target_user) DO UPDATE SET decision = $3, created_at = now()`,
        [user.id, targetUserId, decision]);

      if (decision !== "liked") return json(200, { matched: false });

      // Match se anche l'altro mi ha messo "liked"
      const recip = await c.query(
        `SELECT 1 FROM swipes WHERE user_id = $1 AND target_user = $2 AND decision = 'liked'`,
        [targetUserId, user.id]);
      if (recip.rowCount === 0) return json(200, { matched: false });

      const [a, b] = [user.id, targetUserId].sort(); // ordine stabile per UNIQUE
      const m = await c.query(
        `INSERT INTO matches (user_a, user_b) VALUES ($1,$2)
         ON CONFLICT (user_a, user_b) DO NOTHING RETURNING id`, [a, b]);
      return json(200, { matched: true, matchId: m.rows[0]?.id || null });
    });
  })
});
