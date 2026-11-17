// Lab 03 · A REST API for notes: API Gateway (HTTP API) → Lambda → DynamoDB
//
//   GET    /notes        list notes (newest first)
//   POST   /notes        create a note   { "title": "...", "text": "..." }
//   GET    /notes/{id}   read one note
//   DELETE /notes/{id}   delete one note
//
// Table: partition key "id" (String). Set TABLE_NAME in the function's environment.

import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import {
  DynamoDBDocumentClient, PutCommand, GetCommand, DeleteCommand, ScanCommand,
} from '@aws-sdk/lib-dynamodb';
import { randomUUID } from 'node:crypto';

const db = DynamoDBDocumentClient.from(new DynamoDBClient({}));
const TABLE = process.env.TABLE_NAME;

const json = (statusCode, body) => ({
  statusCode,
  headers: { 'content-type': 'application/json' },
  body: body === undefined ? '' : JSON.stringify(body),
});

function parseBody(event) {
  if (!event.body) return {};
  const raw = event.isBase64Encoded ? Buffer.from(event.body, 'base64').toString('utf8') : event.body;
  try { return JSON.parse(raw); } catch { return null; }
}

async function listNotes() {
  // Scan is fine for a small lab table. For big tables, design a Query with a key instead.
  const { Items = [] } = await db.send(new ScanCommand({ TableName: TABLE, Limit: 100 }));
  Items.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return json(200, { items: Items });
}

async function createNote(event) {
  const body = parseBody(event);
  if (body === null) return json(400, { error: 'Body must be JSON' });

  const title = String(body.title ?? '').trim().slice(0, 100);
  const text = String(body.text ?? '').trim().slice(0, 2000);
  if (!title) return json(400, { error: '"title" is required' });

  const note = { id: randomUUID(), title, text, createdAt: new Date().toISOString() };
  await db.send(new PutCommand({ TableName: TABLE, Item: note }));
  return json(201, note);
}

async function getNote(id) {
  const { Item } = await db.send(new GetCommand({ TableName: TABLE, Key: { id } }));
  return Item ? json(200, Item) : json(404, { error: 'Note not found' });
}

async function deleteNote(id) {
  await db.send(new DeleteCommand({ TableName: TABLE, Key: { id } }));
  return json(204);
}

export const handler = async (event) => {
  const method = event.requestContext?.http?.method;
  const path = (event.rawPath ?? '/').replace(/\/+$/, '') || '/';
  console.log(JSON.stringify({ method, path }));

  try {
    if (path === '/notes' && method === 'GET') return await listNotes();
    if (path === '/notes' && method === 'POST') return await createNote(event);

    const match = path.match(/^\/notes\/([\w-]{1,64})$/);
    if (match && method === 'GET') return await getNote(match[1]);
    if (match && method === 'DELETE') return await deleteNote(match[1]);

    return json(404, { error: `No route for ${method} ${path}` });
  } catch (err) {
    console.error(err);
    return json(500, { error: 'Internal error, check the CloudWatch logs' });
  }
};
