// Lab 02 · Your first Lambda function
//
// Works three ways without changes:
//   1. The console "Test" button          → event = the JSON you type
//   2. A function URL in the browser       → event.queryStringParameters = ?name=...
//   3. aws lambda invoke from the terminal → event = --payload JSON

const GREETING = process.env.GREETING ?? 'Hello';

export const handler = async (event, context) => {
  // Everything you log goes to CloudWatch Logs (Monitor tab → View CloudWatch logs).
  console.log('Event received:', JSON.stringify(event));

  const name = event?.queryStringParameters?.name ?? event?.name ?? 'cloud builder';

  const body = {
    message: `${GREETING}, ${name}!`,
    requestId: context?.awsRequestId,
    region: process.env.AWS_REGION,
    memoryMB: Number(context?.memoryLimitInMB),
    at: new Date().toISOString(),
  };

  // A function URL turns this into a real HTTP response.
  return {
    statusCode: 200,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  };
};
