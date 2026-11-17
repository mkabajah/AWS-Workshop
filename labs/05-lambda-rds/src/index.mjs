// Lab 05 · Lambda talks to a PostgreSQL database in Amazon RDS
//
// The function runs inside the VPC, next to the database. It reads the
// database password from Secrets Manager (never from code or env vars),
// connects over SSL, and runs SQL.
//
// Invoke it with a test event:
//   { "action": "init" }                                  create the table
//   { "action": "add", "name": "Coffee", "price": 3.5 }   insert a product
//   { "action": "list" }                                  list products
//
// Environment:
//   DB_HOST              the RDS endpoint
//   DB_NAME              database name (default "postgres")
//   SECRET_ARN           the secret RDS created for the master user
//   NODE_EXTRA_CA_CERTS  /var/runtime/ca-cert.pem  (lets Node verify the RDS certificate)

import pg from 'pg';
import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

const secrets = new SecretsManagerClient({});
let pool; // reused across invocations of a warm function: one connection, not one per request

async function getPool() {
  if (pool) return pool;

  const { SecretString } = await secrets.send(new GetSecretValueCommand({ SecretId: process.env.SECRET_ARN }));
  const { username, password } = JSON.parse(SecretString);

  pool = new pg.Pool({
    host: process.env.DB_HOST,
    port: 5432,
    database: process.env.DB_NAME || 'postgres',
    user: username,
    password,
    ssl: { rejectUnauthorized: true }, // encrypted and verified
    max: 1, // a Lambda instance handles one request at a time
    connectionTimeoutMillis: 5000,
    idleTimeoutMillis: 60000,
  });
  return pool;
}

const actions = {
  async init(db) {
    await db.query(`
      CREATE TABLE IF NOT EXISTS products (
        id         SERIAL PRIMARY KEY,
        name       TEXT NOT NULL,
        price      NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
      )`);
    return { ok: true, message: 'Table "products" is ready' };
  },

  async add(db, event) {
    const name = String(event.name ?? '').trim().slice(0, 100);
    const price = Number(event.price);
    if (!name || !Number.isFinite(price) || price < 0) {
      return { ok: false, error: 'Send a "name" and a non-negative "price"' };
    }
    // $1 and $2 are parameters: the driver escapes them, so SQL injection is impossible.
    const { rows } = await db.query(
      'INSERT INTO products (name, price) VALUES ($1, $2) RETURNING id, name, price, created_at',
      [name, price],
    );
    return { ok: true, product: rows[0] };
  },

  async list(db) {
    const { rows } = await db.query('SELECT id, name, price, created_at FROM products ORDER BY id DESC LIMIT 50');
    return { ok: true, count: rows.length, products: rows };
  },
};

export const handler = async (event) => {
  const action = actions[event?.action];
  if (!action) return { ok: false, error: 'Unknown action. Use "init", "add" or "list".' };

  const db = await getPool();
  const result = await action(db, event);
  console.log(JSON.stringify({ action: event.action, ok: result.ok }));
  return result;
};
