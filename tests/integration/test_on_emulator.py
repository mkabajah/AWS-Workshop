"""Lab 09 · Integration tests: the real Lambda code against real AWS APIs, on AWS Emulator.

The unit tests in tests/ replace AWS with fakes. These tests call the emulator instead,
so S3, DynamoDB and SQS really validate the requests, keep state and return real errors.

    source labs/09-aws-emulator/emulator-env.sh    # with the emulator running
    pytest tests/integration -v

Without AWS_ENDPOINT_URL they are skipped. With it, they first prove they are on the
emulator (account 000000000000) and refuse to run against real AWS.
"""

import json
import os
import sys
import time
import uuid

import boto3
import pytest
from botocore.exceptions import ClientError

from conftest import ROOT, http_event, load_lambda, parse

sys.path.insert(0, str(ROOT / "labs/09-aws-emulator"))
from guard import check_emulator  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("AWS_ENDPOINT_URL"),
    reason="AWS Emulator not configured: source labs/09-aws-emulator/emulator-env.sh",
)

RUN = uuid.uuid4().hex[:8]


@pytest.fixture(scope="module", autouse=True)
def on_emulator():
    check_emulator()  # raises (and fails every test) if this would reach real AWS


def make_table(name, *keys):
    db = boto3.client("dynamodb")
    db.create_table(
        TableName=name,
        KeySchema=[{"AttributeName": k, "KeyType": t} for k, t in zip(keys, ("HASH", "RANGE"), strict=False)],
        AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k in keys],
        BillingMode="PAY_PER_REQUEST",
    )
    db.get_waiter("table_exists").wait(TableName=name)
    return boto3.resource("dynamodb").Table(name)


def make_bucket(name):
    boto3.client("s3").create_bucket(Bucket=name)
    return name


# ── Lab 03 · notes API on a real (emulated) DynamoDB table ─────────────────


def test_lab03_notes_crud_on_dynamodb(monkeypatch):
    notes = load_lambda("labs/03-api-dynamodb/src/lambda_function.py", "it_lab03")
    monkeypatch.setattr(notes, "table", make_table(f"it-notes-{RUN}", "id"))

    created = notes.lambda_handler(http_event("POST", "/notes", json.dumps({"title": "On the emulator"})), None)
    assert created["statusCode"] == 201
    note_id = parse(created)["id"]

    assert parse(notes.lambda_handler(http_event("GET", f"/notes/{note_id}"), None))["title"] == "On the emulator"
    assert [n["id"] for n in parse(notes.lambda_handler(http_event("GET", "/notes"), None))["items"]] == [note_id]
    assert notes.lambda_handler(http_event("DELETE", f"/notes/{note_id}"), None)["statusCode"] == 204
    assert notes.lambda_handler(http_event("GET", f"/notes/{note_id}"), None)["statusCode"] == 404


# ── Lab 07 · the capstone API and S3 trigger on one table ──────────────────


def test_lab07_counter_guestbook_and_uploads(monkeypatch):
    api = load_lambda("labs/07-capstone/lambda/api/lambda_function.py", "it_lab07_api")
    on_upload = load_lambda("labs/07-capstone/lambda/on-upload/lambda_function.py", "it_lab07_on_upload")
    table = make_table(f"it-site-{RUN}", "pk", "sk")
    monkeypatch.setattr(api, "table", table)
    monkeypatch.setattr(on_upload, "table", table)

    # The ADD update is atomic on the real API too
    assert parse(api.lambda_handler(http_event("POST", "/api/visits"), None))["visits"] == 1
    assert parse(api.lambda_handler(http_event("POST", "/api/visits"), None))["visits"] == 2

    api.lambda_handler(http_event("POST", "/api/messages", json.dumps({"name": "Dana", "message": "Hi"})), None)
    time.sleep(0.01)
    api.lambda_handler(http_event("POST", "/api/messages", json.dumps({"name": "Omar", "message": "Yo"})), None)
    names = [m["name"] for m in parse(api.lambda_handler(http_event("GET", "/api/messages"), None))["items"]]
    assert names == ["Omar", "Dana"]  # the Query with ScanIndexForward=False really sorts newest first

    # Upload a real object, then hand the trigger the event S3 would send
    bucket = make_bucket(f"it-uploads-{RUN}")
    boto3.client("s3").put_object(Bucket=bucket, Key="my photo.jpg", Body=b"x" * 2048)
    event = {
        "Records": [
            {
                "eventTime": "2026-11-17T10:00:00.000Z",
                "s3": {"bucket": {"name": bucket}, "object": {"key": "my+photo.jpg", "size": 2048}},
            }
        ]
    }
    assert on_upload.lambda_handler(event, None) == {"recorded": 1}
    uploads = parse(api.lambda_handler(http_event("GET", "/api/uploads"), None))["items"]
    assert uploads == [{"key": "my photo.jpg", "size": 2048, "at": "2026-11-17T10:00:00.000Z"}]


# ── Lab 04 · a real SQS queue: only the bad message goes back ──────────────


def test_lab04_sqs_batch_with_one_bad_message():
    process_order = load_lambda("labs/04-event-triggers/src/process-order/lambda_function.py", "it_lab04_orders")
    sqs = boto3.client("sqs")
    url = sqs.create_queue(QueueName=f"it-orders-{RUN}")["QueueUrl"]

    sqs.send_message(QueueUrl=url, MessageBody=json.dumps({"orderId": "good", "items": [{"price": 2}]}))
    sqs.send_message(QueueUrl=url, MessageBody=json.dumps({"orderId": "bad", "items": []}))

    messages = []
    for _ in range(5):  # SQS may return fewer messages per call than asked for
        messages += sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=1).get("Messages", [])
        if len(messages) >= 2:
            break
    assert len(messages) == 2

    # The event Lambda builds from the same messages
    event = {"Records": [{"messageId": m["MessageId"], "body": m["Body"]} for m in messages]}
    failures = process_order.lambda_handler(event, None)["batchItemFailures"]

    bad_id = next(m["MessageId"] for m in messages if json.loads(m["Body"])["orderId"] == "bad")
    assert failures == [{"itemIdentifier": bad_id}]


# ── Lab 04 · S3 metadata + SNS (skipped if this emulator build lacks SNS) ──


def test_lab04_upload_notification(monkeypatch):
    on_upload = load_lambda("labs/04-event-triggers/src/on-upload/lambda_function.py", "it_lab04_on_upload")
    try:
        topic = boto3.client("sns").create_topic(Name=f"it-uploads-{RUN}")["TopicArn"]
    except ClientError as err:
        pytest.skip(f"SNS not available on this emulator: {err.response['Error']['Code']}")
    monkeypatch.setenv("TOPIC_ARN", topic)

    bucket = make_bucket(f"it-files-{RUN}")
    boto3.client("s3").put_object(Bucket=bucket, Key="cv.pdf", Body=b"%PDF" * 512, ContentType="application/pdf")

    event = {"Records": [{"s3": {"bucket": {"name": bucket}, "object": {"key": "cv.pdf"}}}]}
    assert on_upload.lambda_handler(event, None) == {"processed": 1}


# ── Real errors, not mocks: the emulator validates requests like AWS ───────


def test_the_emulator_rejects_what_aws_rejects():
    with pytest.raises(ClientError) as err:
        boto3.client("dynamodb").get_item(TableName=f"does-not-exist-{RUN}", Key={"id": {"S": "1"}})
    assert err.value.response["Error"]["Code"] == "ResourceNotFoundException"

    with pytest.raises(ClientError) as err:
        boto3.client("s3").get_object(Bucket=make_bucket(f"it-empty-{RUN}"), Key="missing.txt")
    assert err.value.response["Error"]["Code"] in {"NoSuchKey", "404"}
