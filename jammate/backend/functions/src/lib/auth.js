/* Validazione del token Microsoft Entra External ID (JWT Bearer).
 * Non gestiamo password: ci fidiamo solo di token firmati da Entra (vedi ADR 0004).
 * La firma è verificata con le chiavi pubbliche (JWKS) del tenant. */
"use strict";
const jwt = require("jsonwebtoken");
const jwksClient = require("jwks-rsa");
const { query } = require("./db");

let client;
function getJwks() {
  if (!client) {
    client = jwksClient({ jwksUri: process.env.ENTRA_JWKS_URI, cache: true, rateLimit: true });
  }
  return client;
}
function getKey(header, cb) {
  getJwks().getSigningKey(header.kid, (err, key) => {
    if (err) return cb(err);
    cb(null, key.getPublicKey());
  });
}

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

/** Verifica il Bearer token e restituisce i claim. Lancia HttpError(401) se invalido. */
function verifyToken(request) {
  const auth = request.headers.get("authorization") || "";
  const m = auth.match(/^Bearer\s+(.+)$/i);
  if (!m) throw new HttpError(401, "Token mancante");
  return new Promise((resolve, reject) => {
    jwt.verify(m[1], getKey, {
      audience: process.env.ENTRA_AUDIENCE,
      issuer: process.env.ENTRA_ISSUER,
      algorithms: ["RS256"]
    }, (err, decoded) => err ? reject(new HttpError(401, "Token non valido")) : resolve(decoded));
  });
}

/** Restituisce l'utente applicativo (riga `users`), creandolo al primo accesso (JIT). */
async function getCurrentUser(request) {
  const claims = await verifyToken(request);
  const sub = claims.sub;
  const email = claims.email || claims.preferred_username || null;
  const rows = await query(
    `INSERT INTO users (entra_sub, email, display_name)
       VALUES ($1, $2, $3)
     ON CONFLICT (entra_sub) DO UPDATE SET email = EXCLUDED.email
     RETURNING id, email, display_name, deleted_at`,
    [sub, email, claims.name || null]
  );
  const user = rows[0];
  if (user.deleted_at) throw new HttpError(403, "Account disattivato");
  return user;
}

module.exports = { verifyToken, getCurrentUser, HttpError };
