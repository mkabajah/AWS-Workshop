"""Lab 04 · Trigger 1: S3 -> Lambda -> SNS.

Runs when a file is uploaded to the bucket. It reads the file's details
and sends an email-style notification through an SNS topic.

Environment: TOPIC_ARN
"""

import os
from urllib.parse import unquote_plus

import boto3

s3 = boto3.client("s3")
sns = boto3.client("sns")


def lambda_handler(event, context):
    records = event.get("Records", [])

    for record in records:
        bucket = record["s3"]["bucket"]["name"]
        # S3 URL-encodes keys in events, with spaces as "+".
        key = unquote_plus(record["s3"]["object"]["key"])

        # Ask S3 for the object's metadata (needs s3:GetObject on the bucket).
        head = s3.head_object(Bucket=bucket, Key=key)
        size_kb = f"{head.get('ContentLength', 0) / 1024:.1f}"
        content_type = head.get("ContentType", "unknown")

        print(f"New upload: s3://{bucket}/{key} ({size_kb} KB, {content_type})")

        sns.publish(
            TopicArn=os.environ["TOPIC_ARN"],
            Subject=f"New upload: {key}"[:100],
            Message=(
                f"A file was uploaded.\n\nBucket: {bucket}\nFile: {key}\nSize: {size_kb} KB\nType: {content_type}"
            ),
        )

    return {"processed": len(records)}
