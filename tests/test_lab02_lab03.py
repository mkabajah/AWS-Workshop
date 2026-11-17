"""Lab 02 (hello) and Lab 03 (notes API) · run with: pytest"""

import json

import pytest

from conftest import FakeTable, http_event, load_lambda, parse

hello = load_lambda("labs/02-lambda-basics/src/lambda_function.py", "lab02_hello")
notes = load_lambda("labs/03-api-dynamodb/src/lambda_function.py", "lab03_notes")


# ── Lab 02 ─────────────────────────────────────────────────────────────────


def test_lab02_greets_the_name_from_a_console_test_event(context):
    res = hello.lambda_handler({"name": "Dana"}, context)
    assert res["statusCode"] == 200
    assert parse(res)["message"] == "Hello, Dana!"
    assert parse(res)["requestId"] == "req-1"
    assert parse(res)["memoryMB"] == 128


def test_lab02_greets_the_name_from_a_function_url_query_string(context):
    res = hello.lambda_handler(http_event("GET", "/", query={"name": "Omar"}), context)
    assert parse(res)["message"] == "Hello, Omar!"


def test_lab02_has_a_default_name():
    assert parse(hello.lambda_handler({}, None))["message"] == "Hello, cloud builder!"


# ── Lab 03 ─────────────────────────────────────────────────────────────────


@pytest.fixture
def table(monkeypatch):
    fake = FakeTable(("id",))
    monkeypatch.setattr(notes, "table", fake)
    return fake


def test_lab03_create_list_read_and_delete_a_note(table):
    created = notes.lambda_handler(http_event("POST", "/notes", json.dumps({"title": "First", "text": "Hi"})), None)
    assert created["statusCode"] == 201
    note_id = parse(created)["id"]

    assert len(parse(notes.lambda_handler(http_event("GET", "/notes"), None))["items"]) == 1
    assert parse(notes.lambda_handler(http_event("GET", f"/notes/{note_id}"), None))["title"] == "First"
    assert notes.lambda_handler(http_event("DELETE", f"/notes/{note_id}"), None)["statusCode"] == 204
    assert notes.lambda_handler(http_event("GET", f"/notes/{note_id}"), None)["statusCode"] == 404


def test_lab03_lists_newest_first_and_accepts_base64_bodies(table):
    table.put_item(Item={"id": "a", "title": "Old", "text": "", "createdAt": "2026-01-01T00:00:00+00:00"})
    notes.lambda_handler(http_event("POST", "/notes", json.dumps({"title": "New"}), base64_body=True), None)

    titles = [n["title"] for n in parse(notes.lambda_handler(http_event("GET", "/notes/"), None))["items"]]
    assert titles == ["New", "Old"]


def test_lab03_rejects_bad_input_and_unknown_routes(table):
    assert notes.lambda_handler(http_event("POST", "/notes", "{oops"), None)["statusCode"] == 400
    assert (
        notes.lambda_handler(http_event("POST", "/notes", json.dumps({"text": "no title"})), None)["statusCode"] == 400
    )
    assert notes.lambda_handler(http_event("POST", "/notes", "[1, 2]"), None)["statusCode"] == 400
    assert notes.lambda_handler(http_event("PUT", "/notes"), None)["statusCode"] == 404
    assert notes.lambda_handler(http_event("GET", "/notes/../../etc"), None)["statusCode"] == 404
