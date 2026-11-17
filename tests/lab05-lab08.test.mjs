import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { SecretsManagerClient } from '@aws-sdk/client-secrets-manager';
import { BedrockRuntimeClient } from '@aws-sdk/client-bedrock-runtime';
import { fakeClient, httpEvent, parse } from './helpers.mjs';

// ── Lab 05: fake Secrets Manager and a fake PostgreSQL ────────────────────
// (Needs `npm ci --omit=dev` in labs/05-lambda-rds/src, like the deploy does.)
const pg = createRequire(new URL('../labs/05-lambda-rds/src/index.mjs', import.meta.url))('pg');

const secretCalls = fakeClient(SecretsManagerClient, {
  GetSecretValueCommand: () => ({ SecretString: JSON.stringify({ username: 'postgres', password: 's3cret' }) }),
});

const rows = [];
const queries = [];
let poolConfig;
const RealPool = pg.Pool;
pg.Pool = class FakePool {
  constructor(config) { poolConfig = config; }
  async query(sql, params = []) {
    queries.push({ sql, params });
    if (sql.startsWith('INSERT')) {
      const row = { id: rows.length + 1, name: params[0], price: String(params[1]), created_at: new Date() };
      rows.push(row);
      return { rows: [row] };
    }
    if (sql.startsWith('SELECT')) return { rows: [...rows].reverse() };
    return { rows: [] };
  }
};

process.env.SECRET_ARN = 'arn:aws:secretsmanager:eu-central-1:111111111111:secret:rds';
process.env.DB_HOST = 'db.example.internal';
const { handler: products } = await import('../labs/05-lambda-rds/src/index.mjs');

test('lab05: init, add and list products', async () => {
  assert.equal((await products({ action: 'init' })).ok, true);
  assert.match(queries[0].sql, /CREATE TABLE IF NOT EXISTS products/);

  const added = await products({ action: 'add', name: '  Coffee ', price: 3.5 });
  assert.equal(added.product.name, 'Coffee');
  assert.deepEqual(queries.at(-1).params, ['Coffee', 3.5]); // values go as parameters, never into the SQL text

  const listed = await products({ action: 'list' });
  assert.equal(listed.count, 1);
});

test('lab05: connects once, over verified SSL, with the secret', async () => {
  await products({ action: 'list' });
  assert.equal(secretCalls.length, 1); // the pool is reused across invocations
  assert.deepEqual(poolConfig.ssl, { rejectUnauthorized: true });
  assert.equal(poolConfig.user, 'postgres');
  assert.equal(poolConfig.host, 'db.example.internal');
});

test('lab05: rejects bad input and unknown actions', async () => {
  assert.equal((await products({ action: 'add', name: 'Tea', price: -1 })).ok, false);
  assert.equal((await products({ action: 'drop' })).ok, false);
});

test.after(() => { pg.Pool = RealPool; });

// ── Lab 08: fake Bedrock ───────────────────────────────────────────────────
const bedrockCalls = fakeClient(BedrockRuntimeClient, {
  ConverseCommand: () => ({
    output: { message: { content: [{ text: 'She builds cloud apps on AWS.' }] } },
    usage: { inputTokens: 80, outputTokens: 9, totalTokens: 89 },
    stopReason: 'end_turn',
  }),
});
process.env.MODEL_ID = 'us.amazon.nova-micro-v1:0';
process.env.SITE_CONTEXT = 'Dana builds cloud apps.';
const { handler: ask } = await import('../labs/08-ai-bedrock/src/index.mjs');

test('lab08: answers a question from an HTTP request, with a token cap', async () => {
  const res = await ask(httpEvent('POST', '/', JSON.stringify({ question: 'What does Dana build?' })));
  assert.equal(res.statusCode, 200);
  assert.equal(parse(res).answer, 'She builds cloud apps on AWS.');

  const { input } = bedrockCalls.at(-1);
  assert.equal(input.modelId, 'us.amazon.nova-micro-v1:0');
  assert.equal(input.inferenceConfig.maxTokens, 300);
  assert.match(input.system[0].text, /Dana builds cloud apps/);
});

test('lab08: accepts console test events and rejects empty questions', async () => {
  assert.equal((await ask({ question: 'Hi?' })).statusCode, 200);
  assert.equal((await ask(httpEvent('POST', '/', '{}'))).statusCode, 400);
  assert.equal((await ask(httpEvent('POST', '/', 'not json'))).statusCode, 400);
});
