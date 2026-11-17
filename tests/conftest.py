"""Shared test helpers: load a lab's Lambda file and replace AWS with in-memory fakes.

The tests never call AWS, so they run with no account and no credentials.
"""

import base64
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# boto3 needs a Region to build clients, even when every call is faked.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")


def load_lambda(relative_path, name):
    """Import labs/.../lambda_function.py under a unique module name.

    Every lab names its file lambda_function.py (the console default), so each one is
    loaded under its own name to keep them apart.
    """
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def http_event(method, path, body=None, *, base64_body=False, query=None):
    """An API Gateway HTTP API (payload v2) or function URL event."""
    if body is not None and base64_body:
        body = base64.b64encode(body.encode()).decode()
    return {
        "version": "2.0",
        "rawPath": path,
        "queryStringParameters": query,
        "requestContext": {"http": {"method": method}},
        "body": body,
        "isBase64Encoded": base64_body,
    }


def parse(response):
    return json.loads(response["body"]) if response.get("body") else None


class Recorder:
    """A fake boto3 client: each method returns a canned answer and records its call."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls = []

    def __getattr__(self, method):
        if method not in self.answers:
            raise AttributeError(f"Unexpected call: {method}")

        def call(*args, **kwargs):
            self.calls.append((method, kwargs or args))
            answer = self.answers[method]
            return answer(*args, **kwargs) if callable(answer) else answer

        return call


class FakeTable:
    """A tiny in-memory stand-in for a boto3 DynamoDB Table."""

    def __init__(self, key_names=("id",)):
        self.key_names = key_names
        self.items = {}

    def _key(self, key):
        return tuple(key[name] for name in self.key_names)

    def put_item(self, Item):
        self.items[self._key(Item)] = dict(Item)
        return {}

    def get_item(self, Key):
        item = self.items.get(self._key(Key))
        return {"Item": dict(item)} if item else {}

    def delete_item(self, Key):
        self.items.pop(self._key(Key), None)
        return {}

    def scan(self, Limit=None):
        return {"Items": [dict(i) for i in list(self.items.values())[:Limit]]}

    def update_item(self, Key, ExpressionAttributeValues, **_):
        item = self.items.setdefault(self._key(Key), {**Key, "count": 0})
        item["count"] += ExpressionAttributeValues[":one"]
        return {"Attributes": {"count": item["count"]}}

    def query(self, KeyConditionExpression, ScanIndexForward=True, Limit=None):
        pk = KeyConditionExpression.get_expression()["values"][1]
        items = sorted((i for i in self.items.values() if i["pk"] == pk), key=lambda i: i["sk"])
        if not ScanIndexForward:
            items.reverse()
        return {"Items": [dict(i) for i in items[:Limit]]}


class Boom:
    """A table where every call fails, to test error handling."""

    def __getattr__(self, name):
        def fail(**_):
            raise RuntimeError("boom")

        return fail


@pytest.fixture
def context():
    class Context:
        aws_request_id = "req-1"
        memory_limit_in_mb = "128"

    return Context()
