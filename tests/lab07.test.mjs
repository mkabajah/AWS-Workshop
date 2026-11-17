// Unit tests for both Lambda functions, with DynamoDB replaced by an in-memory table.
// Lab 07 capstone · run with: npm test

import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb';

// ── A tiny in-memory stand-in for DynamoDB ────────────────────────────────
const table = new Map();
const keyOf = ({ pk, sk }) => `${pk}|${sk}`;

DynamoDBDocumentClient.prototype.send = async function send(command) {
  const input = command.input;
  switch (command.constructor.name) {
    case 'GetCommand':
      return { Item: table.get(keyOf(input.Key)) };
    case 'PutCommand':
      table.set(keyOf(input.Item), structuredClone(input.Item));
      return {};
    case 'UpdateCommand': {
      const item = table.get(keyOf(input.Key)) ?? { ...input.Key, count: 0 };
      item.count += input.ExpressionAttributeValues[':one'];
      table.set(keyOf(input.Key), item);
      return { Attributes: { count: item.count } };
    }
    case 'QueryCommand': {
      const pk = input.ExpressionAttributeValues[':pk'];
      const items = [...table.values()].filter((i) => i.pk === pk).sort((a, b) => a.sk.localeCompare(b.sk));
      if (input.ScanIndexForward === false) items.reverse();
      return { Items: items.slice(0, input.Limit) };
    }
    default:
      throw new Error(`Unexpected command ${command.constructor.name}`);
  }
};

process.env.TABLE_NAME = 'test-table';
const { handler: api } = await import('../labs/07-capstone/lambda/api/index.mjs');
const { handler: onUpload } = await import('../labs/07-capstone/lambda/on-upload/index.mjs');

const request = (method, path, body, { base64 = false } = {}) => ({
  rawPath: path,
  requestContext: { http: { method } },
  body: body === undefined ? undefined : base64 ? Buffer.from(body).toString('base64') : body,
  isBase64Encoded: base64,
});
const json = (res) => JSON.parse(res.body);

beforeEach(() => table.clear());

// ── API ────────────────────────────────────────────────────────────────────

test('visits start at 0 and count up', async () => {
  assert.equal(json(await api(request('GET', '/api/visits'))).visits, 0);
  assert.equal(json(await api(request('POST', '/api/visits'))).visits, 1);
  assert.equal(json(await api(request('POST', '/api/visits'))).visits, 2);
  assert.equal(json(await api(request('GET', '/api/visits'))).visits, 2);
});

test('a guestbook message is saved and listed newest first', async () => {
  const first = await api(request('POST', '/api/messages', JSON.stringify({ name: 'Dana', message: 'Hello!' })));
  assert.equal(first.statusCode, 201);
  await new Promise((r) => setTimeout(r, 5));
  await api(request('POST', '/api/messages', JSON.stringify({ name: 'Omar', message: 'Second' }), { base64: true }));

  const { items } = json(await api(request('GET', '/api/messages')));
  assert.deepEqual(items.map((m) => m.name), ['Omar', 'Dana']);
  assert.deepEqual(Object.keys(items[0]).sort(), ['at', 'message', 'name']); // no internal keys leak out
});

test('messages are trimmed and length-limited', async () => {
  await api(request('POST', '/api/messages', JSON.stringify({ name: `  ${'x'.repeat(60)}  `, message: 'a\n\n  b' })));
  const [item] = json(await api(request('GET', '/api/messages'))).items;
  assert.equal(item.name.length, 40);
  assert.equal(item.message, 'a b');
});

test('bad guestbook input is rejected with 400', async () => {
  assert.equal((await api(request('POST', '/api/messages', '{not json'))).statusCode, 400);
  assert.equal((await api(request('POST', '/api/messages', JSON.stringify({ name: ' ', message: 'hi' })))).statusCode, 400);
  assert.equal((await api(request('POST', '/api/messages', JSON.stringify({ name: 'Dana' })))).statusCode, 400);
  assert.equal(json(await api(request('GET', '/api/messages'))).items.length, 0);
});

test('unknown routes return 404', async () => {
  assert.equal((await api(request('GET', '/api/nope'))).statusCode, 404);
  assert.equal((await api(request('DELETE', '/api/messages'))).statusCode, 404);
});

test('database errors return 500 without details', async () => {
  const original = DynamoDBDocumentClient.prototype.send;
  DynamoDBDocumentClient.prototype.send = async () => { throw new Error('boom'); };
  try {
    const res = await api(request('GET', '/api/visits'));
    assert.equal(res.statusCode, 500);
    assert.equal(json(res).error, 'Something went wrong');
  } finally {
    DynamoDBDocumentClient.prototype.send = original;
  }
});

// ── S3 trigger ─────────────────────────────────────────────────────────────

test('an S3 upload event is recorded and shows in /api/uploads', async () => {
  const event = {
    Records: [{
      eventTime: '2026-11-16T10:00:00.000Z',
      s3: { bucket: { name: 'uploads' }, object: { key: 'my+photo%281%29.jpg', size: 20480 } },
    }],
  };
  assert.deepEqual(await onUpload(event), { recorded: 1 });

  const { items } = json(await api(request('GET', '/api/uploads')));
  assert.deepEqual(items, [{ key: 'my photo(1).jpg', size: 20480, at: '2026-11-16T10:00:00.000Z' }]);
});
