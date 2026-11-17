// Lab 04 · Trigger 3: a schedule (EventBridge) → Lambda → SNS
// Runs on a timer, like cron. It counts the files in the uploads bucket
// and emails a short report through SNS.
//
// Environment: BUCKET_NAME, TOPIC_ARN

import { S3Client, ListObjectsV2Command } from '@aws-sdk/client-s3';
import { SNSClient, PublishCommand } from '@aws-sdk/client-sns';

const s3 = new S3Client({});
const sns = new SNSClient({});

async function summarizeBucket(bucket) {
  let files = 0;
  let bytes = 0;
  let token;
  do {
    const page = await s3.send(new ListObjectsV2Command({ Bucket: bucket, ContinuationToken: token }));
    for (const obj of page.Contents ?? []) {
      files += 1;
      bytes += obj.Size ?? 0;
    }
    token = page.IsTruncated ? page.NextContinuationToken : undefined;
  } while (token);
  return { files, megabytes: Number((bytes / 1024 / 1024).toFixed(2)) };
}

export const handler = async (event) => {
  const bucket = process.env.BUCKET_NAME;
  const { files, megabytes } = await summarizeBucket(bucket);
  const report = `Daily report for ${bucket}: ${files} files, ${megabytes} MB in total.`;

  console.log(report, `(triggered by ${event?.source ?? 'manual test'})`);

  await sns.send(new PublishCommand({
    TopicArn: process.env.TOPIC_ARN,
    Subject: 'Daily uploads report',
    Message: report,
  }));
  return { files, megabytes };
};
