"""Lab 02 · Your first Lambda function.

Works three ways without changes:
  1. The console "Test" button          -> event = the JSON you type
  2. A function URL in the browser       -> event["queryStringParameters"] = ?name=...
  3. aws lambda invoke from the terminal -> event = the --payload JSON
"""

import json
import os
from datetime import datetime, timezone

GREETING = os.environ.get("GREETING", "Hello")


def lambda_handler(event, context):
    # Everything you print goes to CloudWatch Logs (Monitor tab -> View CloudWatch logs).
    print("Event received:", json.dumps(event))

    event = event or {}
    query = event.get("queryStringParameters") or {}
    name = query.get("name") or event.get("name") or "cloud builder"

    body = {
        "message": f"{GREETING}, {name}!",
        "requestId": getattr(context, "aws_request_id", None),
        "region": os.environ.get("AWS_REGION"),
        "memoryMB": int(getattr(context, "memory_limit_in_mb", 0) or 0),
        "at": datetime.now(timezone.utc).isoformat(),
    }

    # A function URL turns this dictionary into a real HTTP response.
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
