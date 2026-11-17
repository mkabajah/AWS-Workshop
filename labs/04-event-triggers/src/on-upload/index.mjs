// Lab 04 · Trigger 1: S3 → Lambda → SNS
// Runs when a file is uploaded to the bucket. It reads the file's details
// and sends an email-style notification through an SNS topic.
//
// Environment: TOPIC_ARN

import { S3Client, HeadObjectCommand } from '@aws-sdk/client-s3';
import { SNSClient, PublishCommand } from '@aws-sdk/client-sns';

const s3 = new S3Client({});
const sns = new SNSClient({});

// S3 URL-encodes keys in events, with spaces as "+".
const decodeKey = (key) => decodeURIComponent(key.replace(/\+/g, ' '));

export const handler = async (event) => {
  for (const record of event.Records ?? []) {
    const bucket = record.s3.bucket.name;
    const key = decodeKey(record.s3.object.key);

    // Ask S3 for the object's metadata (needs s3:GetObject on the bucket).
    const head = await s3.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));
    const sizeKb = ((head.ContentLength ?? 0) / 1024).toFixed(1);

    console.log(`New upload: s3://${bucket}/${key} (${sizeKb} KB, ${head.ContentType})`);

    await sns.send(new PublishCommand({
      TopicArn: process.env.TOPIC_ARN,
      Subject: `New upload: ${key}`.slice(0, 100),
      Message: `A file was uploaded.\n\nBucket: ${bucket}\nFile: ${key}\nSize: ${sizeKb} KB\nType: ${head.ContentType}`,
    }));
  }
  return { processed: event.Records?.length ?? 0 };
};
