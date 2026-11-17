"""Runs by itself whenever a file lands in the uploads bucket: an S3 event trigger.

Nobody calls this function. S3 does. It records each new file in DynamoDB,
and the website's "Latest uploads" list reads it from there.
"""

import os
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3

table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "website"))


def lambda_handler(event, context):
    records = event.get("Records", [])

    for record in records:
        # S3 URL-encodes object keys in events, with spaces as "+".
        key = unquote_plus(record["s3"]["object"]["key"])
        size = record["s3"]["object"].get("size", 0)
        at = record.get("eventTime") or datetime.now(timezone.utc).isoformat()

        print(f"New upload: {key} ({size} bytes) in {record['s3']['bucket']['name']}")

        table.put_item(Item={"pk": "FILE", "sk": f"{at}#{key}", "key": key, "size": size, "at": at})

    return {"recorded": len(records)}
