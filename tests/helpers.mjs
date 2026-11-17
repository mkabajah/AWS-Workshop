// Test helpers: replace AWS SDK clients with fakes, so tests run with no AWS account.

/**
 * Replaces Client.prototype.send. `handlers` maps a command name
 * (e.g. "PublishCommand") to a function that receives the command input.
 * Returns the list of calls, so tests can check what the code sent.
 */
export function fakeClient(ClientClass, handlers) {
  const calls = [];
  ClientClass.prototype.send = async function send(command) {
    const name = command.constructor.name;
    calls.push({ name, input: command.input });
    const handler = handlers[name];
    if (!handler) throw new Error(`Unexpected ${name}`);
    return handler(command.input);
  };
  return calls;
}

/** An API Gateway HTTP API (payload v2) or function URL event. */
export function httpEvent(method, path, body, { base64 = false, query } = {}) {
  return {
    version: '2.0',
    rawPath: path,
    queryStringParameters: query,
    requestContext: { http: { method } },
    body: body === undefined ? undefined : base64 ? Buffer.from(body).toString('base64') : body,
    isBase64Encoded: base64,
  };
}

export const parse = (response) => (response.body ? JSON.parse(response.body) : undefined);
