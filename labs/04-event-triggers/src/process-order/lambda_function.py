"""Lab 04 · Trigger 2: SQS queue -> Lambda (with a dead-letter queue).

Lambda pulls messages from the queue in batches. A message that fails is
retried; after 3 failures SQS moves it to the dead-letter queue (DLQ).

Returning batchItemFailures retries only the bad messages, not the whole batch
(needs "Report batch item failures" turned on in the trigger).
"""

import json
import math


def process_order(order):
    if not isinstance(order, dict) or not order.get("orderId"):
        raise ValueError("Missing orderId")
    items = order.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Order has no items")

    try:
        total = sum(float(item["price"]) * float(item.get("qty", 1)) for item in items)
    except (KeyError, TypeError, ValueError) as err:
        raise ValueError("Invalid price or quantity") from err
    if not math.isfinite(total):
        raise ValueError("Invalid price or quantity")

    # A real system would charge a card, save to a database, send an email...
    print(f"Order {order['orderId']}: {len(items)} items, total ${total:.2f}")
    return total


def lambda_handler(event, context):
    batch_item_failures = []

    for record in event.get("Records", []):
        try:
            process_order(json.loads(record["body"]))
        except Exception as err:  # noqa: BLE001 - any failure sends this one message back to the queue
            print(f"Message {record['messageId']} failed: {err}")
            batch_item_failures.append({"itemIdentifier": record["messageId"]})

    return {"batchItemFailures": batch_item_failures}
