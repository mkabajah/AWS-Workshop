"""The website's API: one small Lambda behind API Gateway. CloudFront sends /api/* here.

  GET  /api/visits    current visitor count
  POST /api/visits    add 1 to the count, return the new total
  GET  /api/messages  latest 20 guestbook messages
  POST /api/messages  save a guestbook message
  GET  /api/uploads   latest 10 files recorded by the upload trigger (stage 3)

Everything lives in one DynamoDB table, grouped by partition key:
  STATS / visits          the counter
  MSG   / <time>#<uuid>   guestbook messages, newest last
  FILE  / <time>#<key>    uploads recorded by the trigger

boto3 is part of the Python Lambda runtime: nothing to install.
"""

import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "website"))

MAX_NAME = 40
MAX_MESSAGE = 280
VISITS_KEY = {"pk": "STATS", "sk": "visits"}


# ── Responses ──────────────────────────────────────────────────────────────


def _to_json(value):
    # DynamoDB returns numbers as Decimal; JSON needs int or float.
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def reply(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(body, default=_to_json),
    }


def bad_request(error):
    return reply(400, {"error": error})


# ── Data access ────────────────────────────────────────────────────────────


def get_visits():
    item = table.get_item(Key=VISITS_KEY).get("Item")
    return item["count"] if item else 0


def add_visit():
    result = table.update_item(
        Key=VISITS_KEY,
        UpdateExpression="ADD #count :one",  # atomic: safe with many visitors at once
        ExpressionAttributeNames={"#count": "count"},
        ExpressionAttributeValues={":one": 1},
        ReturnValues="UPDATED_NEW",
    )
    return result["Attributes"]["count"]


def latest(pk, limit):
    result = table.query(
        KeyConditionExpression=Key("pk").eq(pk),
        ScanIndexForward=False,  # newest first: sort keys start with an ISO timestamp
        Limit=limit,
    )
    return result.get("Items", [])


# ── Input ──────────────────────────────────────────────────────────────────


def read_json(event):
    """Return the JSON body as a dict, {} when empty, or None when it is not valid JSON."""
    raw = event.get("body")
    if not raw:
        return {}
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw)
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def clean(value, max_length):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:max_length]


def pick(item, *fields):
    return {field: item.get(field) for field in fields}


# ── Routes ─────────────────────────────────────────────────────────────────


def route_get_visits(event):
    return reply(200, {"visits": get_visits()})


def route_add_visit(event):
    return reply(200, {"visits": add_visit()})


def route_list_messages(event):
    items = latest("MSG", 20)
    return reply(200, {"items": [pick(i, "name", "message", "at") for i in items]})


def route_save_message(event):
    body = read_json(event)
    if body is None:
        return bad_request("Body must be JSON")

    name = clean(body.get("name"), MAX_NAME)
    message = clean(body.get("message"), MAX_MESSAGE)
    if not name or not message:
        return bad_request("Name and message are required")

    at = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={"pk": "MSG", "sk": f"{at}#{uuid.uuid4()}", "name": name, "message": message, "at": at})
    return reply(201, {"saved": True})


def route_list_uploads(event):
    items = latest("FILE", 10)
    return reply(200, {"items": [pick(i, "key", "size", "at") for i in items]})


ROUTES = {
    "GET /api/visits": route_get_visits,
    "POST /api/visits": route_add_visit,
    "GET /api/messages": route_list_messages,
    "POST /api/messages": route_save_message,
    "GET /api/uploads": route_list_uploads,
}


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method")
    route = f"{method} {event.get('rawPath')}"
    print(json.dumps({"route": route}))  # one line per request in CloudWatch Logs

    handle = ROUTES.get(route)
    if handle is None:
        return reply(404, {"error": "Not found"})

    try:
        return handle(event)
    except Exception as err:  # noqa: BLE001 - log it, never leak details to visitors
        print(json.dumps({"route": route, "error": type(err).__name__, "message": str(err)}))
        return reply(500, {"error": "Something went wrong"})
