"""Lab 03 · A REST API for notes: API Gateway (HTTP API) -> Lambda -> DynamoDB.

  GET    /notes        list notes (newest first)
  POST   /notes        create a note   {"title": "...", "text": "..."}
  GET    /notes/{id}   read one note
  DELETE /notes/{id}   delete one note

Table: partition key "id" (String). Set TABLE_NAME in the function's environment.
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

table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "notes"))

NOTE_PATH = re.compile(r"^/notes/([\w-]{1,64})$")


def _to_json(value):
    # DynamoDB returns numbers as Decimal; JSON needs int or float.
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def respond(status_code, body=None):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": "" if body is None else json.dumps(body, default=_to_json),
    }


def parse_body(event):
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


def list_notes():
    # Scan is fine for a small lab table. For big tables, design a Query with a key instead.
    items = table.scan(Limit=100).get("Items", [])
    items.sort(key=lambda note: note.get("createdAt", ""), reverse=True)
    return respond(200, {"items": items})


def create_note(event):
    body = parse_body(event)
    if body is None:
        return respond(400, {"error": "Body must be a JSON object"})

    title = str(body.get("title") or "").strip()[:100]
    text = str(body.get("text") or "").strip()[:2000]
    if not title:
        return respond(400, {"error": '"title" is required'})

    note = {
        "id": str(uuid.uuid4()),
        "title": title,
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=note)
    return respond(201, note)


def get_note(note_id):
    item = table.get_item(Key={"id": note_id}).get("Item")
    return respond(200, item) if item else respond(404, {"error": "Note not found"})


def delete_note(note_id):
    table.delete_item(Key={"id": note_id})
    return respond(204)


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method")
    path = (event.get("rawPath") or "/").rstrip("/") or "/"
    print(json.dumps({"method": method, "path": path}))

    try:
        if path == "/notes" and method == "GET":
            return list_notes()
        if path == "/notes" and method == "POST":
            return create_note(event)

        match = NOTE_PATH.match(path)
        if match and method == "GET":
            return get_note(match.group(1))
        if match and method == "DELETE":
            return delete_note(match.group(1))

        return respond(404, {"error": f"No route for {method} {path}"})
    except Exception as err:  # noqa: BLE001 - one place to log every unexpected error
        print(f"ERROR {type(err).__name__}: {err}")
        return respond(500, {"error": "Internal error, check the CloudWatch logs"})
