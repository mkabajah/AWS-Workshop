"""Lab 07 capstone · the website API and the S3 upload trigger, with DynamoDB in memory · run with: pytest"""

import json
import time

import pytest

from conftest import Boom, FakeTable, http_event, load_lambda, parse

api = load_lambda("labs/07-capstone/lambda/api/lambda_function.py", "lab07_api")
on_upload = load_lambda("labs/07-capstone/lambda/on-upload/lambda_function.py", "lab07_on_upload")


@pytest.fixture(autouse=True)
def table(monkeypatch):
    fake = FakeTable(("pk", "sk"))
    monkeypatch.setattr(api, "table", fake)
    monkeypatch.setattr(on_upload, "table", fake)
    return fake


def call(method, path, body=None, **kwargs):
    return api.lambda_handler(http_event(method, path, body, **kwargs), None)


# ── API ────────────────────────────────────────────────────────────────────


def test_visits_start_at_0_and_count_up():
    assert parse(call("GET", "/api/visits"))["visits"] == 0
    assert parse(call("POST", "/api/visits"))["visits"] == 1
    assert parse(call("POST", "/api/visits"))["visits"] == 2
    assert parse(call("GET", "/api/visits"))["visits"] == 2


def test_a_guestbook_message_is_saved_and_listed_newest_first():
    first = call("POST", "/api/messages", json.dumps({"name": "Dana", "message": "Hello!"}))
    assert first["statusCode"] == 201
    time.sleep(0.002)
    call("POST", "/api/messages", json.dumps({"name": "Omar", "message": "Second"}), base64_body=True)

    items = parse(call("GET", "/api/messages"))["items"]
    assert [m["name"] for m in items] == ["Omar", "Dana"]
    assert sorted(items[0]) == ["at", "message", "name"]  # no internal keys leak out


def test_messages_are_trimmed_and_length_limited():
    call("POST", "/api/messages", json.dumps({"name": f"  {'x' * 60}  ", "message": "a\n\n  b"}))
    [item] = parse(call("GET", "/api/messages"))["items"]
    assert len(item["name"]) == 40
    assert item["message"] == "a b"


def test_bad_guestbook_input_is_rejected_with_400():
    assert call("POST", "/api/messages", "{not json")["statusCode"] == 400
    assert call("POST", "/api/messages", json.dumps({"name": " ", "message": "hi"}))["statusCode"] == 400
    assert call("POST", "/api/messages", json.dumps({"name": "Dana"}))["statusCode"] == 400
    assert parse(call("GET", "/api/messages"))["items"] == []


def test_unknown_routes_return_404():
    assert call("GET", "/api/nope")["statusCode"] == 404
    assert call("DELETE", "/api/messages")["statusCode"] == 404


def test_database_errors_return_500_without_details(monkeypatch):
    monkeypatch.setattr(api, "table", Boom())
    res = call("GET", "/api/visits")
    assert res["statusCode"] == 500
    assert parse(res)["error"] == "Something went wrong"


# ── S3 trigger ─────────────────────────────────────────────────────────────


def test_an_s3_upload_event_is_recorded_and_shows_in_api_uploads():
    event = {
        "Records": [
            {
                "eventTime": "2026-11-16T10:00:00.000Z",
                "s3": {"bucket": {"name": "uploads"}, "object": {"key": "my+photo%281%29.jpg", "size": 20480}},
            }
        ]
    }
    assert on_upload.lambda_handler(event, None) == {"recorded": 1}

    items = parse(call("GET", "/api/uploads"))["items"]
    assert items == [{"key": "my photo(1).jpg", "size": 20480, "at": "2026-11-16T10:00:00.000Z"}]
