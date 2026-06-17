/* /v1/posts — feed sociale (#11): post, reazioni multiple, commenti. */
"use strict";
const { app } = require("@azure/functions");
const { json, withAuth } = require("../lib/http");
const { query } = require("../lib/db");

// GET /posts — feed con autore, conteggio reazioni per emoji, mia reazione, n. commenti
app.http("posts-list", {
  methods: ["GET"], authLevel: "anonymous", route: "posts",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT p.id, p.body AS text, p.image_url AS image, p.created_at AS "ts",
              p.author_id AS "authorId", u.display_name AS name, mp.avatar, mp.color, mp.photo_url AS photo,
              COALESCE((SELECT jsonb_object_agg(emoji, c)
                          FROM (SELECT emoji, count(*) c FROM post_reactions WHERE post_id=p.id GROUP BY emoji) s),
                       '{}'::jsonb) AS reactions,
              (SELECT emoji FROM post_reactions WHERE post_id=p.id AND user_id=$1) AS "myReaction",
              (SELECT count(*)::int FROM post_comments WHERE post_id=p.id) AS "commentCount"
         FROM posts p
         JOIN users u ON u.id=p.author_id
         LEFT JOIN musician_profiles mp ON mp.user_id=u.id
        ORDER BY p.created_at DESC LIMIT 50`, [user.id]);
    return json(200, rows);
  })
});

// POST /posts — pubblica un post (testo e/o immagine)
app.http("posts-create", {
  methods: ["POST"], authLevel: "anonymous", route: "posts",
  handler: withAuth(async (req, ctx, user) => {
    const b = await req.json();
    if (!b.text && !b.image) return json(400, { error: "testo o immagine richiesti" });
    const [row] = await query(
      `INSERT INTO posts (author_id, body, image_url) VALUES ($1,$2,$3) RETURNING id, created_at AS "ts"`,
      [user.id, b.text || null, b.image || null]);
    return json(201, row);
  })
});

// PUT /posts/{id}/reaction — imposta/cambia/rimuove la mia reazione
app.http("posts-react", {
  methods: ["PUT"], authLevel: "anonymous", route: "posts/{id}/reaction",
  handler: withAuth(async (req, ctx, user) => {
    const id = req.params.id, { emoji } = await req.json();
    if (!emoji) { await query(`DELETE FROM post_reactions WHERE post_id=$1 AND user_id=$2`, [id, user.id]); return json(200, { reaction: null }); }
    await query(
      `INSERT INTO post_reactions (post_id, user_id, emoji) VALUES ($1,$2,$3)
       ON CONFLICT (post_id, user_id) DO UPDATE SET emoji=$3, created_at=now()`, [id, user.id, emoji]);
    return json(200, { reaction: emoji });
  })
});

// GET /posts/{id}/comments
app.http("posts-comments", {
  methods: ["GET"], authLevel: "anonymous", route: "posts/{id}/comments",
  handler: withAuth(async (req, ctx, user) => {
    const rows = await query(
      `SELECT c.id, c.body AS text, c.created_at AS ts, u.display_name AS name
         FROM post_comments c JOIN users u ON u.id=c.author_id
        WHERE c.post_id=$1 ORDER BY c.created_at`, [req.params.id]);
    return json(200, rows);
  })
});

// POST /posts/{id}/comments — commenta
app.http("posts-comment-add", {
  methods: ["POST"], authLevel: "anonymous", route: "posts/{id}/comments",
  handler: withAuth(async (req, ctx, user) => {
    const { text } = await req.json();
    if (!text) return json(400, { error: "testo mancante" });
    const [row] = await query(
      `INSERT INTO post_comments (post_id, author_id, body) VALUES ($1,$2,$3) RETURNING id, created_at AS ts`,
      [req.params.id, user.id, text]);
    return json(201, row);
  })
});
