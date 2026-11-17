import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb';
import { fakeClient, httpEvent, parse } from './helpers.mjs';

// ── Lab 02 ─────────────────────────────────────────────────────────────────
const { handler: hello } = await import('../labs/02-lambda-basics/src/index.mjs');

test('lab02: greets the name from a console test event', async () => {
  const res = await hello({ name: 'Dana' }, { awsRequestId: 'req-1', memoryLimitInMB: '128' });
  assert.equal(res.statusCode, 200);
  assert.equal(parse(res).message, 'Hello, Dana!');
  assert.equal(parse(res).requestId, 'req-1');
});

test('lab02: greets the name from a function URL query string', async () => {
  const res = await hello(httpEvent('GET', '/', undefined, { query: { name: 'Omar' } }), {});
  assert.equal(parse(res).message, 'Hello, Omar!');
});

test('lab02: has a default name', async () => {
  assert.equal(parse(await hello({}, {})).message, 'Hello, cloud builder!');
});

// ── Lab 03 ─────────────────────────────────────────────────────────────────
const table = new Map();
fakeClient(DynamoDBDocumentClient, {
  PutCommand: ({ Item }) => { table.set(Item.id, structuredClone(Item)); return {}; },
  GetCommand: ({ Key }) => ({ Item: table.get(Key.id) }),
  DeleteCommand: ({ Key }) => { table.delete(Key.id); return {}; },
  ScanCommand: () => ({ Items: [...table.values()] }),
});
process.env.TABLE_NAME = 'notes';
const { handler: notes } = await import('../labs/03-api-dynamodb/src/index.mjs');

beforeEach(() => table.clear());

test('lab03: create, list, read and delete a note', async () => {
  const created = await notes(httpEvent('POST', '/notes', JSON.stringify({ title: 'First', text: 'Hi' })));
  assert.equal(created.statusCode, 201);
  const { id } = parse(created);

  assert.equal(parse(await notes(httpEvent('GET', '/notes'))).items.length, 1);
  assert.equal(parse(await notes(httpEvent('GET', `/notes/${id}`))).title, 'First');
  assert.equal((await notes(httpEvent('DELETE', `/notes/${id}`))).statusCode, 204);
  assert.equal((await notes(httpEvent('GET', `/notes/${id}`))).statusCode, 404);
});

test('lab03: lists newest first and accepts base64 bodies', async () => {
  await notes(httpEvent('POST', '/notes', JSON.stringify({ title: 'Old' })));
  await new Promise((r) => setTimeout(r, 5));
  await notes(httpEvent('POST', '/notes/', JSON.stringify({ title: 'New' }), { base64: true }));
  assert.deepEqual(parse(await notes(httpEvent('GET', '/notes'))).items.map((n) => n.title), ['New', 'Old']);
});

test('lab03: rejects bad input and unknown routes', async () => {
  assert.equal((await notes(httpEvent('POST', '/notes', '{oops'))).statusCode, 400);
  assert.equal((await notes(httpEvent('POST', '/notes', JSON.stringify({ text: 'no title' })))).statusCode, 400);
  assert.equal((await notes(httpEvent('PUT', '/notes'))).statusCode, 404);
  assert.equal((await notes(httpEvent('GET', '/notes/../../etc'))).statusCode, 404);
});
