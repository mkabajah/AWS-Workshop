// The website's API: one small Lambda behind API Gateway. CloudFront sends /api/* here.
//
//   GET  /api/visits    current visitor count
//   POST /api/visits    add 1 to the count, return the new total
//   GET  /api/messages  latest 20 guestbook messages
//   POST /api/messages  save a guestbook message
//   GET  /api/uploads   latest 10 files recorded by the upload trigger (stage 3)
//
// Everything lives in one DynamoDB table, grouped by partition key:
//   STATS / visits          the counter
//   MSG   / <time>#<uuid>   guestbook messages, newest last
//   FILE  / <time>#<key>    uploads recorded by the trigger
//
// The AWS SDK v3 is part of the Node.js Lambda runtime: nothing to install.

import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand, PutCommand, QueryCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb';
import { randomUUID } from 'node:crypto';

const db = DynamoDBDocumentClient.from(new DynamoDBClient({}));
const TABLE = process.env.TABLE_NAME;

const MAX_NAME = 40;
const MAX_MESSAGE = 280;

// ── Responses ──────────────────────────────────────────────────────────────

const reply = (statusCode, body) => ({
  statusCode,
  headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  body: JSON.stringify(body),
});

const badRequest = (error) => reply(400, { error });

// ── Data access ────────────────────────────────────────────────────────────

const VISITS_KEY = { pk: 'STATS', sk: 'visits' };

async function getVisits() {
  const { Item } = await db.send(new GetCommand({ TableName: TABLE, Key: VISITS_KEY }));
  return Item?.count ?? 0;
}

async function addVisit() {
  const { Attributes } = await db.send(new UpdateCommand({
    TableName: TABLE,
    Key: VISITS_KEY,
    UpdateExpression: 'ADD #count :one', // atomic: safe with many visitors at once
    ExpressionAttributeNames: { '#count': 'count' },
    ExpressionAttributeValues: { ':one': 1 },
    ReturnValues: 'UPDATED_NEW',
  }));
  return Attributes.count;
}

async function latest(pk, limit) {
  const { Items = [] } = await db.send(new QueryCommand({
    TableName: TABLE,
    KeyConditionExpression: 'pk = :pk',
    ExpressionAttributeValues: { ':pk': pk },
    ScanIndexForward: false, // newest first: sort keys start with an ISO timestamp
    Limit: limit,
  }));
  return Items;
}

// ── Input ──────────────────────────────────────────────────────────────────

function readJson(event) {
  if (!event.body) return {};
  const raw = event.isBase64Encoded ? Buffer.from(event.body, 'base64').toString('utf8') : event.body;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

const clean = (value, max) => String(value ?? '').replace(/\s+/g, ' ').trim().slice(0, max);

// ── Routes ─────────────────────────────────────────────────────────────────

const routes = {
  'GET /api/visits': async () => reply(200, { visits: await getVisits() }),

  'POST /api/visits': async () => reply(200, { visits: await addVisit() }),

  'GET /api/messages': async () => {
    const items = await latest('MSG', 20);
    return reply(200, { items: items.map(({ name, message, at }) => ({ name, message, at })) });
  },

  'POST /api/messages': async (event) => {
    const body = readJson(event);
    if (body === null) return badRequest('Body must be JSON');

    const name = clean(body.name, MAX_NAME);
    const message = clean(body.message, MAX_MESSAGE);
    if (!name || !message) return badRequest('Name and message are required');

    const at = new Date().toISOString();
    await db.send(new PutCommand({
      TableName: TABLE,
      Item: { pk: 'MSG', sk: `${at}#${randomUUID()}`, name, message, at },
    }));
    return reply(201, { saved: true });
  },

  'GET /api/uploads': async () => {
    const items = await latest('FILE', 10);
    return reply(200, { items: items.map(({ key, size, at }) => ({ key, size, at })) });
  },
};

export const handler = async (event) => {
  const route = `${event.requestContext?.http?.method} ${event.rawPath}`;
  console.log(JSON.stringify({ route })); // one line per request in CloudWatch Logs

  const handle = routes[route];
  if (!handle) return reply(404, { error: 'Not found' });

  try {
    return await handle(event);
  } catch (err) {
    console.error(JSON.stringify({ route, error: err.name, message: err.message }));
    return reply(500, { error: 'Something went wrong' });
  }
};
