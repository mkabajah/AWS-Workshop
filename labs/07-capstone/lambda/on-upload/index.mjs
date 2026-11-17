// Runs by itself whenever a file lands in the uploads bucket: an S3 event trigger.
// Nobody calls this function. S3 does. It records each new file in DynamoDB,
// and the website's "Latest uploads" list reads it from there.

import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, PutCommand } from '@aws-sdk/lib-dynamodb';

const db = DynamoDBDocumentClient.from(new DynamoDBClient({}));
const TABLE = process.env.TABLE_NAME;

// S3 URL-encodes object keys in events, with spaces as "+".
const decodeKey = (key) => decodeURIComponent(key.replace(/\+/g, ' '));

export const handler = async (event) => {
  const records = event.Records ?? [];

  for (const record of records) {
    const key = decodeKey(record.s3.object.key);
    const size = record.s3.object.size ?? 0;
    const at = record.eventTime ?? new Date().toISOString();

    console.log(`New upload: ${key} (${size} bytes) in ${record.s3.bucket.name}`);

    await db.send(new PutCommand({
      TableName: TABLE,
      Item: { pk: 'FILE', sk: `${at}#${key}`, key, size, at },
    }));
  }

  return { recorded: records.length };
};
