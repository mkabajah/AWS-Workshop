#!/usr/bin/env python3
"""Lab 09 · A tour of AWS on your laptop: S3, DynamoDB, SQS, then your own Lambda code.

    source labs/09-aws-emulator/emulator-env.sh
    python labs/09-aws-emulator/try_it.py

Nothing here has an endpoint or a key in it. boto3 reads AWS_ENDPOINT_URL and the emulator's
credentials from the environment, exactly as it reads real ones on AWS.
"""

import importlib.util
import json
import sys
import time
from pathlib import Path

import boto3
from guard import NotTheEmulator, check_emulator

REPO = Path(__file__).resolve().parents[2]
RUN = time.strftime("%H%M%S")


def step(title):
    print(f"\n── {title} " + "─" * max(0, 60 - len(title)))


def s3_tour():
    step("1 · S3: a bucket and a file")
    s3 = boto3.client("s3")
    bucket = f"lab09-{RUN}"
    s3.create_bucket(Bucket=bucket)
    s3.put_object(Bucket=bucket, Key="hello.txt", Body=b"Hello from my laptop", ContentType="text/plain")
    body = s3.get_object(Bucket=bucket, Key="hello.txt")["Body"].read().decode()
    print(f"created s3://{bucket}, read back: {body!r}")
    print("buckets:", [b["Name"] for b in s3.list_buckets()["Buckets"]])


def dynamodb_tour():
    step("2 · DynamoDB: a table and an item")
    db = boto3.client("dynamodb")
    table = f"lab09-notes-{RUN}"
    db.create_table(
        TableName=table,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    db.get_waiter("table_exists").wait(TableName=table)
    db.put_item(TableName=table, Item={"id": {"S": "1"}, "title": {"S": "First note"}})
    item = db.get_item(TableName=table, Key={"id": {"S": "1"}})["Item"]
    print(f"table {table}: {item}")
    return table


def sqs_tour():
    step("3 · SQS: send and receive a message")
    sqs = boto3.client("sqs")
    url = sqs.create_queue(QueueName=f"lab09-orders-{RUN}")["QueueUrl"]
    sqs.send_message(QueueUrl=url, MessageBody=json.dumps({"orderId": "A1", "items": [{"price": 4.5}]}))
    messages = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=1, WaitTimeSeconds=1).get("Messages", [])
    print(f"queue {url.rsplit('/', 1)[-1]}: received {[m['Body'] for m in messages]}")


def run_lab03_locally(table):
    step("4 · Your Lambda code (lab 03) against the emulator")
    spec = importlib.util.spec_from_file_location("lab03", REPO / "labs/03-api-dynamodb/src/lambda_function.py")
    lab03 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab03)
    lab03.table = boto3.resource("dynamodb").Table(table)  # the same line runs in Lambda, with TABLE_NAME

    def call(method, path, body=None):
        event = {"rawPath": path, "requestContext": {"http": {"method": method}}, "body": body}
        response = lab03.lambda_handler(event, None)
        print(f"{method:6} {path:<14} -> {response['statusCode']} {response['body'][:70]}")
        return response

    call("POST", "/notes", json.dumps({"title": "Written by lambda_handler", "text": "no deploy needed"}))
    call("GET", "/notes")


def main():
    try:
        account = check_emulator()
    except NotTheEmulator as err:
        sys.exit(f"Stopped: {err}")
    print(f"Connected to AWS Emulator, account {account}. Nothing here reaches real AWS.")

    s3_tour()
    table = dynamodb_tour()
    sqs_tour()
    run_lab03_locally(table)

    step("Done")
    print("Stop the emulator (Ctrl+C) and everything above disappears: nothing to clean up, nothing to pay.")


if __name__ == "__main__":
    main()
