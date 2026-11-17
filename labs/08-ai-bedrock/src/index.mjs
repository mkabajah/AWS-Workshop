// Lab 08 · Add AI to your product: Lambda → Amazon Bedrock
//
// A small "ask me" endpoint for your website: send a question, get an answer
// from a foundation model, written as your site's assistant.
//
//   POST /   { "question": "What does this person build?" }
//
// Environment:
//   MODEL_ID       a model or inference profile ID from the Bedrock console
//   SITE_CONTEXT   a few lines about you that the assistant may use

import { BedrockRuntimeClient, ConverseCommand } from '@aws-sdk/client-bedrock-runtime';

const bedrock = new BedrockRuntimeClient({});

const MAX_QUESTION = 500;

const reply = (statusCode, body) => ({
  statusCode,
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
});

function readQuestion(event) {
  // Console test events send { "question": ... } directly; HTTP requests send a body.
  if (typeof event?.question === 'string') return event.question;
  if (!event?.body) return '';
  const raw = event.isBase64Encoded ? Buffer.from(event.body, 'base64').toString('utf8') : event.body;
  try { return String(JSON.parse(raw).question ?? ''); } catch { return ''; }
}

export const handler = async (event) => {
  const question = readQuestion(event).trim().slice(0, MAX_QUESTION);
  if (!question) return reply(400, { error: 'Send {"question": "..."}' });

  const response = await bedrock.send(new ConverseCommand({
    modelId: process.env.MODEL_ID,
    system: [{
      text: 'You are the friendly assistant on a personal website. Answer in at most 3 short sentences. '
        + 'Only use the facts below; if the answer is not there, say you do not know.\n\n'
        + (process.env.SITE_CONTEXT ?? ''),
    }],
    messages: [{ role: 'user', content: [{ text: question }] }],
    inferenceConfig: { maxTokens: 300, temperature: 0.3 }, // a hard cap on cost per request
  }));

  const answer = response.output?.message?.content?.map((part) => part.text ?? '').join('').trim();
  console.log(JSON.stringify({ tokens: response.usage, stopReason: response.stopReason }));

  return reply(200, { answer, tokens: response.usage?.totalTokens });
};
