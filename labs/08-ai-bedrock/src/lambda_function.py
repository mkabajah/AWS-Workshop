"""Lab 08 · Add AI to your product: Lambda -> Amazon Bedrock.

A small "ask me" endpoint for your website: send a question, get an answer
from a foundation model, written as your site's assistant.

  POST /   {"question": "What does this person build?"}

Environment:
  MODEL_ID       a model or inference profile ID from the Bedrock console
  SITE_CONTEXT   a few lines about you that the assistant may use
"""

import base64
import json
import os

import boto3

bedrock = boto3.client("bedrock-runtime")

MAX_QUESTION = 500

SYSTEM_PROMPT = (
    "You are the friendly assistant on a personal website. Answer in at most 3 short sentences. "
    "Only use the facts below; if the answer is not there, say you do not know.\n\n"
)


def reply(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def read_question(event):
    # Console test events send {"question": ...} directly; HTTP requests send a body.
    event = event or {}
    if isinstance(event.get("question"), str):
        return event["question"]
    raw = event.get("body")
    if not raw:
        return ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        return str(json.loads(raw).get("question") or "")
    except (ValueError, AttributeError):
        return ""


def lambda_handler(event, context):
    question = read_question(event).strip()[:MAX_QUESTION]
    if not question:
        return reply(400, {"error": 'Send {"question": "..."}'})

    response = bedrock.converse(
        modelId=os.environ["MODEL_ID"],
        system=[{"text": SYSTEM_PROMPT + os.environ.get("SITE_CONTEXT", "")}],
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.3},  # a hard cap on cost per request
    )

    parts = response.get("output", {}).get("message", {}).get("content", [])
    answer = "".join(part.get("text", "") for part in parts).strip()
    usage = response.get("usage", {})
    print(json.dumps({"tokens": usage, "stopReason": response.get("stopReason")}))

    return reply(200, {"answer": answer, "tokens": usage.get("totalTokens")})
