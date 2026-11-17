"""Lab 04 · the three triggers: S3 upload, SQS queue and a schedule · run with: pytest"""

import json
import os

import pytest

from conftest import Recorder, load_lambda

os.environ["TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:lab04-uploads"
os.environ["BUCKET_NAME"] = "lab04-uploads"

on_upload = load_lambda("labs/04-event-triggers/src/on-upload/lambda_function.py", "lab04_on_upload")
process_order = load_lambda("labs/04-event-triggers/src/process-order/lambda_function.py", "lab04_process_order")
daily_report = load_lambda("labs/04-event-triggers/src/daily-report/lambda_function.py", "lab04_daily_report")


def test_an_s3_upload_is_read_and_announced_on_sns(monkeypatch):
    s3 = Recorder(head_object={"ContentLength": 20480, "ContentType": "image/jpeg"})
    sns = Recorder(publish={"MessageId": "m-1"})
    monkeypatch.setattr(on_upload, "s3", s3)
    monkeypatch.setattr(on_upload, "sns", sns)

    event = {"Records": [{"s3": {"bucket": {"name": "lab04-uploads"}, "object": {"key": "my+photo.jpg"}}}]}
    assert on_upload.lambda_handler(event, None) == {"processed": 1}

    assert s3.calls[-1][1]["Key"] == "my photo.jpg"
    published = sns.calls[-1][1]
    assert "20.0 KB" in published["Message"]
    assert published["TopicArn"] == os.environ["TOPIC_ARN"]


def test_an_order_total_is_computed():
    assert process_order.process_order({"orderId": "A", "items": [{"price": 4.5, "qty": 2}, {"price": 1}]}) == 10
    with pytest.raises(ValueError, match="no items"):
        process_order.process_order({"orderId": "B", "items": []})
    with pytest.raises(ValueError, match="orderId"):
        process_order.process_order({"items": [{"price": 1}]})
    with pytest.raises(ValueError, match="Invalid price"):
        process_order.process_order({"orderId": "C", "items": [{"price": "abc"}]})


def test_only_the_bad_sqs_messages_are_reported_for_retry():
    event = {
        "Records": [
            {"messageId": "good", "body": json.dumps({"orderId": "1", "items": [{"price": 2}]})},
            {"messageId": "bad-json", "body": "{nope"},
            {"messageId": "no-items", "body": json.dumps({"orderId": "2", "items": []})},
        ]
    }
    assert process_order.lambda_handler(event, None) == {
        "batchItemFailures": [{"itemIdentifier": "bad-json"}, {"itemIdentifier": "no-items"}]
    }


def test_the_daily_report_reads_every_page_and_emails_a_summary(monkeypatch):
    mb = 1024 * 1024
    pages = [{"Contents": [{"Size": mb}, {"Size": mb}]}, {"Contents": [{"Size": mb}]}]

    class Paginator:
        def paginate(self, Bucket):
            assert Bucket == "lab04-uploads"
            return iter(pages)

    s3 = Recorder(get_paginator=lambda name: Paginator())
    sns = Recorder(publish={"MessageId": "m-2"})
    monkeypatch.setattr(daily_report, "s3", s3)
    monkeypatch.setattr(daily_report, "sns", sns)

    assert daily_report.lambda_handler({"source": "aws.events"}, None) == {"files": 3, "megabytes": 3.0}
    assert "3 files, 3.0 MB" in sns.calls[-1][1]["Message"]
