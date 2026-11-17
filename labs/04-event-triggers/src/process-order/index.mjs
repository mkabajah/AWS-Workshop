// Lab 04 · Trigger 2: SQS queue → Lambda (with a dead-letter queue)
// Lambda pulls messages from the queue in batches. A message that fails is
// retried; after 3 failures SQS moves it to the dead-letter queue (DLQ).
//
// Returning batchItemFailures retries only the bad messages, not the whole batch
// (needs "Report batch item failures" turned on in the trigger).

function processOrder(order) {
  if (!order.orderId) throw new Error('Missing orderId');
  if (!Array.isArray(order.items) || order.items.length === 0) throw new Error('Order has no items');

  const total = order.items.reduce((sum, item) => sum + Number(item.price) * Number(item.qty ?? 1), 0);
  if (!Number.isFinite(total)) throw new Error('Invalid price or quantity');

  // A real system would charge a card, save to a database, send an email...
  console.log(`Order ${order.orderId}: ${order.items.length} items, total $${total.toFixed(2)}`);
  return total;
}

export const handler = async (event) => {
  const batchItemFailures = [];

  for (const record of event.Records ?? []) {
    try {
      processOrder(JSON.parse(record.body));
    } catch (err) {
      console.error(`Message ${record.messageId} failed: ${err.message}`);
      batchItemFailures.push({ itemIdentifier: record.messageId });
    }
  }

  return { batchItemFailures };
};

export { processOrder };
