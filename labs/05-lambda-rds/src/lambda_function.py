"""Lab 05 · Lambda talks to a PostgreSQL database in Amazon RDS.

The function runs inside the VPC, next to the database. It reads the
database password from Secrets Manager (never from code or env vars),
connects over SSL, and runs SQL.

Invoke it with a test event:
  {"action": "init"}                                  create the table
  {"action": "add", "name": "Coffee", "price": 3.5}   insert a product
  {"action": "list"}                                  list products

Environment:
  DB_HOST     the RDS endpoint
  DB_NAME     database name (default "postgres")
  SECRET_ARN  the secret RDS created for the master user

Driver: pg8000, a pure-Python PostgreSQL driver. scripts/package.py installs it
next to this file together with the RDS certificate bundle (global-bundle.pem).
"""

import json
import math
import os
import ssl
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import boto3
import pg8000.native

secrets = boto3.client("secretsmanager")

# The RDS certificate authorities. Packaged next to this file by scripts/package.py.
CA_BUNDLE = Path(__file__).with_name("global-bundle.pem")

# Reused across invocations of a warm function: one connection, not one per request.
_connection = None


def get_connection():
    global _connection
    if _connection is not None:
        return _connection

    secret = secrets.get_secret_value(SecretId=os.environ["SECRET_ARN"])
    creds = json.loads(secret["SecretString"])

    if not CA_BUNDLE.exists():
        raise RuntimeError("global-bundle.pem is missing: build the zip with scripts/package.py")
    tls = ssl.create_default_context(cafile=str(CA_BUNDLE))  # encrypted and verified

    _connection = pg8000.native.Connection(
        user=creds["username"],
        password=creds["password"],
        host=os.environ["DB_HOST"],
        port=5432,
        database=os.environ.get("DB_NAME") or "postgres",
        ssl_context=tls,
        timeout=10,
    )
    return _connection


def to_json(value):
    """PostgreSQL NUMERIC arrives as Decimal and TIMESTAMPTZ as datetime: make them JSON-friendly."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def rows_as_dicts(db, rows):
    names = [column["name"] for column in db.columns]
    return [dict(zip(names, row, strict=True)) for row in rows]


def init(db, event):
    db.run(
        """
        CREATE TABLE IF NOT EXISTS products (
            id         SERIAL PRIMARY KEY,
            name       TEXT NOT NULL,
            price      NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    return {"ok": True, "message": 'Table "products" is ready'}


def add(db, event):
    name = str(event.get("name") or "").strip()[:100]
    try:
        price = float(event.get("price"))
    except (TypeError, ValueError):
        price = math.nan
    if not name or not math.isfinite(price) or price < 0:
        return {"ok": False, "error": 'Send a "name" and a non-negative "price"'}

    # :name and :price are parameters: the driver sends them separately from the SQL,
    # so SQL injection is impossible.
    rows = db.run(
        "INSERT INTO products (name, price) VALUES (:name, :price) RETURNING id, name, price, created_at",
        name=name,
        price=price,
    )
    return {"ok": True, "product": rows_as_dicts(db, rows)[0]}


def list_products(db, event):
    rows = db.run("SELECT id, name, price, created_at FROM products ORDER BY id DESC LIMIT 50")
    products = rows_as_dicts(db, rows)
    return {"ok": True, "count": len(products), "products": products}


ACTIONS = {"init": init, "add": add, "list": list_products}


def lambda_handler(event, context):
    global _connection
    event = event or {}
    action = ACTIONS.get(event.get("action"))
    if action is None:
        return {"ok": False, "error": 'Unknown action. Use "init", "add" or "list".'}

    try:
        result = action(get_connection(), event)
    except pg8000.native.InterfaceError:
        # The database closed an idle connection: drop it so the next call reconnects.
        _connection = None
        raise

    print(json.dumps({"action": event["action"], "ok": result["ok"]}))
    # Decimal prices and timestamps become plain JSON values.
    return json.loads(json.dumps(result, default=to_json))
