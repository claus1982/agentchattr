/* Connessione a PostgreSQL (Azure Database for PostgreSQL, regione UE).
 * Pool unico riusato tra le invocazioni della stessa istanza Function. */
"use strict";
const { Pool } = require("pg");

let pool;
function getPool() {
  if (!pool) {
    const connectionString = process.env.PG_CONNECTION_STRING;
    if (!connectionString) throw new Error("PG_CONNECTION_STRING mancante");
    pool = new Pool({
      connectionString,
      ssl: { rejectUnauthorized: true }, // Azure PostgreSQL richiede TLS
      max: 5,                            // prudente: le Functions scalano in orizzontale
      idleTimeoutMillis: 30000
    });
  }
  return pool;
}

/** Esegue una query parametrica (mai concatenare input: anti SQL-injection). */
async function query(text, params) {
  const res = await getPool().query(text, params);
  return res.rows;
}

/** Esegue un blocco in transazione. fn riceve un client già in BEGIN. */
async function tx(fn) {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    const out = await fn(client);
    await client.query("COMMIT");
    return out;
  } catch (e) {
    await client.query("ROLLBACK");
    throw e;
  } finally {
    client.release();
  }
}

module.exports = { getPool, query, tx };
