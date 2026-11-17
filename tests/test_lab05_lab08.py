"""Lab 05 (Lambda + RDS) and Lab 08 (Bedrock) · run with: pytest"""

import json
import os
from decimal import Decimal

import pytest

from conftest import Recorder, http_event, load_lambda, parse

os.environ.update(
    DB_HOST="db.example.internal",
    SECRET_ARN="arn:aws:secretsmanager:us-east-1:123456789012:secret:rds-db",
    MODEL_ID="us.amazon.nova-micro-v1:0",
    SITE_CONTEXT="Dana builds cloud apps on AWS.",
)

products = load_lambda("labs/05-lambda-rds/src/lambda_function.py", "lab05_products")
ask = load_lambda("labs/08-ai-bedrock/src/lambda_function.py", "lab08_ask")


# ── Lab 05: a fake PostgreSQL connection ──────────────────────────────────


class FakeConnection:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.queries = []
        self.columns = []
        self.rows = []
        FakeConnection.instances.append(self)

    def run(self, sql, **params):
        self.queries.append((" ".join(sql.split()), params))
        if sql.startswith("INSERT"):
            row = [len(self.rows) + 1, params["name"], Decimal(str(params["price"])), "2026-11-17T10:00:00+00:00"]
            self.rows.append(row)
            self.columns = [{"name": n} for n in ("id", "name", "price", "created_at")]
            return [row]
        if sql.startswith("SELECT"):
            self.columns = [{"name": n} for n in ("id", "name", "price", "created_at")]
            return list(reversed(self.rows))
        return []


@pytest.fixture
def database(monkeypatch, tmp_path):
    bundle = tmp_path / "global-bundle.pem"
    bundle.write_text("test")
    tls_calls = []

    FakeConnection.instances.clear()
    monkeypatch.setattr(products, "_connection", None)
    monkeypatch.setattr(products, "CA_BUNDLE", bundle)
    monkeypatch.setattr(products.pg8000.native, "Connection", FakeConnection)
    monkeypatch.setattr(products.ssl, "create_default_context", lambda cafile: tls_calls.append(cafile) or "tls")
    secrets = Recorder(get_secret_value={"SecretString": json.dumps({"username": "postgres", "password": "pw"})})
    monkeypatch.setattr(products, "secrets", secrets)
    return {"secrets": secrets, "tls": tls_calls, "bundle": str(bundle)}


def test_lab05_init_add_and_list_products(database):
    assert products.lambda_handler({"action": "init"}, None)["ok"] is True
    db = FakeConnection.instances[0]
    assert "CREATE TABLE IF NOT EXISTS products" in db.queries[0][0]

    added = products.lambda_handler({"action": "add", "name": "Coffee", "price": 3.5}, None)
    assert added["product"]["name"] == "Coffee"
    assert added["product"]["price"] == 3.5  # NUMERIC arrives as Decimal and is returned as a number
    sql, params = db.queries[-1]
    assert ":name" in sql and "Coffee" not in sql  # values go as parameters, never into the SQL text
    assert params == {"name": "Coffee", "price": 3.5}

    listed = products.lambda_handler({"action": "list"}, None)
    assert listed["count"] == 1


def test_lab05_connects_once_over_verified_ssl_with_the_secret(database):
    products.lambda_handler({"action": "list"}, None)
    products.lambda_handler({"action": "list"}, None)

    assert len(database["secrets"].calls) == 1  # the connection is reused across invocations
    assert len(FakeConnection.instances) == 1
    assert database["tls"] == [database["bundle"]]  # verified against the RDS certificates
    kwargs = FakeConnection.instances[0].kwargs
    assert kwargs["ssl_context"] == "tls"
    assert kwargs["user"] == "postgres"
    assert kwargs["host"] == "db.example.internal"


def test_lab05_rejects_bad_input_and_unknown_actions(database):
    assert products.lambda_handler({"action": "add", "name": "Tea", "price": -1}, None)["ok"] is False
    assert products.lambda_handler({"action": "add", "name": "Tea", "price": "free"}, None)["ok"] is False
    assert products.lambda_handler({"action": "add", "price": 2}, None)["ok"] is False
    assert products.lambda_handler({"action": "drop"}, None)["ok"] is False


def test_lab05_explains_a_missing_certificate_bundle(database, monkeypatch, tmp_path):
    monkeypatch.setattr(products, "CA_BUNDLE", tmp_path / "missing.pem")
    with pytest.raises(RuntimeError, match="scripts/package.py"):
        products.lambda_handler({"action": "list"}, None)


# ── Lab 08: a fake Bedrock ────────────────────────────────────────────────


@pytest.fixture
def bedrock(monkeypatch):
    fake = Recorder(
        converse={
            "output": {"message": {"content": [{"text": "She builds cloud apps on AWS."}]}},
            "usage": {"inputTokens": 40, "outputTokens": 9, "totalTokens": 49},
            "stopReason": "end_turn",
        }
    )
    monkeypatch.setattr(ask, "bedrock", fake)
    return fake


def test_lab08_answers_a_question_from_an_http_request_with_a_token_cap(bedrock):
    res = ask.lambda_handler(http_event("POST", "/", json.dumps({"question": "What does Dana build?"})), None)
    assert res["statusCode"] == 200
    assert parse(res) == {"answer": "She builds cloud apps on AWS.", "tokens": 49}

    request = bedrock.calls[-1][1]
    assert request["modelId"] == "us.amazon.nova-micro-v1:0"
    assert request["inferenceConfig"]["maxTokens"] == 300
    assert "Dana builds cloud apps" in request["system"][0]["text"]


def test_lab08_accepts_console_test_events_and_rejects_empty_questions(bedrock):
    assert ask.lambda_handler({"question": "Hi?"}, None)["statusCode"] == 200
    assert ask.lambda_handler({"question": "   "}, None)["statusCode"] == 400
    assert ask.lambda_handler(http_event("POST", "/", "{bad json"), None)["statusCode"] == 400
    assert ask.lambda_handler(http_event("POST", "/", "[]"), None)["statusCode"] == 400
    assert len(bedrock.calls) == 1
