"""Lab 04 · Trigger 3: a schedule (EventBridge) -> Lambda -> SNS.

Runs on a timer, like cron. It counts the files in the uploads bucket
and emails a short report through SNS.

Environment: BUCKET_NAME, TOPIC_ARN
"""

import os

import boto3

s3 = boto3.client("s3")
sns = boto3.client("sns")


def summarize_bucket(bucket):
    files = 0
    total_bytes = 0
    # A paginator follows ContinuationToken for you: 1,000 objects per page.
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            files += 1
            total_bytes += obj.get("Size", 0)
    return {"files": files, "megabytes": round(total_bytes / 1024 / 1024, 2)}


def lambda_handler(event, context):
    bucket = os.environ["BUCKET_NAME"]
    summary = summarize_bucket(bucket)
    report = f"Daily report for {bucket}: {summary['files']} files, {summary['megabytes']} MB in total."

    print(report, f"(triggered by {(event or {}).get('source', 'manual test')})")

    sns.publish(
        TopicArn=os.environ["TOPIC_ARN"],
        Subject="Daily uploads report",
        Message=report,
    )
    return summary
