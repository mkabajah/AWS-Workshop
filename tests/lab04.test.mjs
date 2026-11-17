import { test } from 'node:test';
import assert from 'node:assert/strict';
import { S3Client } from '@aws-sdk/client-s3';
import { SNSClient } from '@aws-sdk/client-sns';
import { fakeClient } from './helpers.mjs';

process.env.TOPIC_ARN = 'arn:aws:sns:eu-central-1:111111111111:labs';
process.env.BUCKET_NAME = 'uploads';

const s3Calls = fakeClient(S3Client, {
  HeadObjectCommand: () => ({ ContentLength: 20480, ContentType: 'image/jpeg' }),
  ListObjectsV2Command: ({ ContinuationToken }) => (ContinuationToken
    ? { Contents: [{ Size: 1048576 }], IsTruncated: false }
    : { Contents: [{ Size: 1048576 }, { Size: 1048576 }], IsTruncated: true, NextContinuationToken: 'page-2' }),
});
const snsCalls = fakeClient(SNSClient, { PublishCommand: () => ({ MessageId: 'm-1' }) });

const { handler: onUpload } = await import('../labs/04-event-triggers/src/on-upload/index.mjs');
const { handler: processOrders, processOrder } = await import('../labs/04-event-triggers/src/process-order/index.mjs');
const { handler: dailyReport } = await import('../labs/04-event-triggers/src/daily-report/index.mjs');

test('lab04: an S3 upload is read and announced on SNS', async () => {
  const event = { Records: [{ s3: { bucket: { name: 'uploads' }, object: { key: 'my+photo.jpg' } } }] };
  assert.deepEqual(await onUpload(event), { processed: 1 });
  assert.equal(s3Calls.at(-1).input.Key, 'my photo.jpg');
  assert.match(snsCalls.at(-1).input.Message, /20\.0 KB/);
  assert.equal(snsCalls.at(-1).input.TopicArn, process.env.TOPIC_ARN);
});

test('lab04: an order total is computed', () => {
  assert.equal(processOrder({ orderId: 'A', items: [{ price: 4.5, qty: 2 }, { price: 1 }] }), 10);
  assert.throws(() => processOrder({ orderId: 'B', items: [] }), /no items/);
  assert.throws(() => processOrder({ items: [{ price: 1 }] }), /orderId/);
});

test('lab04: only the bad SQS messages are reported for retry', async () => {
  const event = {
    Records: [
      { messageId: 'ok', body: JSON.stringify({ orderId: 'A', items: [{ price: 2 }] }) },
      { messageId: 'empty', body: JSON.stringify({ orderId: 'B', items: [] }) },
      { messageId: 'garbage', body: 'not json' },
    ],
  };
  assert.deepEqual(await processOrders(event), {
    batchItemFailures: [{ itemIdentifier: 'empty' }, { itemIdentifier: 'garbage' }],
  });
});

test('lab04: the daily report follows S3 pagination and emails a summary', async () => {
  assert.deepEqual(await dailyReport({ source: 'aws.events' }), { files: 3, megabytes: 3 });
  assert.match(snsCalls.at(-1).input.Message, /3 files, 3 MB/);
});
