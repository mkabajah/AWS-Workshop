// Personal website · client code (no framework, no build step).
//
// The CDK app writes /config.json with the deployed stage:
//   { "stage": 1 | 2 | 3, "deployedWith": "AWS CDK" }
// Without it (console, CLI or Amplify deploys) the page stays a static site.

const REQUEST_TIMEOUT_MS = 8000;
const UPLOAD_REFRESH_MS = 5000;

const $ = (selector) => document.querySelector(selector);

// ── Helpers ────────────────────────────────────────────────────────────────

async function getConfig() {
  try {
    const res = await fetch('/config.json', { cache: 'no-store' });
    if (res.ok) return await res.json();
  } catch {
    // No config: static site only.
  }
  return { stage: 1 };
}

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    ...options,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
  return body;
}

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
function timeAgo(iso) {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  if (!Number.isFinite(seconds)) return '';
  const units = [['day', 86400], ['hour', 3600], ['minute', 60]];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return 'just now';
}

// Builds a feed item with textContent only: visitors' words never become HTML.
function feedItem(title, meta, text) {
  const li = document.createElement('li');
  const header = document.createElement('div');
  header.className = 'meta';
  const who = document.createElement('span');
  who.className = 'who';
  who.textContent = title;
  const when = document.createElement('span');
  when.textContent = meta;
  header.append(who, when);
  li.append(header);
  if (text) {
    const p = document.createElement('p');
    p.className = 'text';
    p.textContent = text;
    li.append(p);
  }
  return li;
}

function showEmpty(list, message) {
  const li = document.createElement('li');
  li.className = 'empty';
  li.textContent = message;
  list.replaceChildren(li);
}

function showFeature(name) {
  document.querySelectorAll(`[data-feature="${name}"]`).forEach((el) => { el.hidden = false; });
}

function markStagesLive(stage) {
  document.querySelectorAll('.stage').forEach((el) => {
    const live = Number(el.dataset.stage) <= stage;
    el.classList.toggle('is-live', live);
    el.querySelector('.status').textContent = live ? 'Live' : 'Next';
  });
}

// ── Stage 2: visitor counter ───────────────────────────────────────────────

async function initVisits() {
  // Count each browser once per session, so refreshing doesn't inflate the number.
  let alreadyCounted = false;
  try { alreadyCounted = sessionStorage.getItem('counted') === '1'; } catch { /* storage blocked */ }

  try {
    const { visits } = await api('/visits', { method: alreadyCounted ? 'GET' : 'POST' });
    $('#visits').textContent = Number(visits).toLocaleString();
    try { sessionStorage.setItem('counted', '1'); } catch { /* storage blocked */ }
  } catch {
    $('#visits').textContent = '—';
  }
}

// ── Stage 2: guestbook ─────────────────────────────────────────────────────

async function loadMessages() {
  const list = $('#messages');
  try {
    const { items } = await api('/messages');
    if (items.length === 0) return showEmpty(list, 'No messages yet. Be the first!');
    list.replaceChildren(...items.map((m) => feedItem(m.name, timeAgo(m.at), m.message)));
  } catch {
    showEmpty(list, 'Messages are unavailable right now.');
  }
}

function initGuestbook() {
  const form = $('#guestbook-form');
  const status = $('#gb-status');
  const message = $('#gb-message');
  const count = $('#gb-count');

  message.addEventListener('input', () => {
    count.textContent = `${message.value.length}/280`;
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = $('#gb-name').value.trim();
    const text = message.value.trim();

    status.className = 'form-status';
    if (!name || !text) {
      status.textContent = 'Please add your name and a message.';
      status.classList.add('is-error');
      return;
    }

    const button = form.querySelector('button');
    button.disabled = true;
    status.textContent = 'Saving…';
    try {
      await api('/messages', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name, message: text }),
      });
      message.value = '';
      count.textContent = '0/280';
      status.textContent = 'Thank you! Your message is saved.';
      status.classList.add('is-ok');
      await loadMessages();
    } catch (err) {
      status.textContent = `Could not save: ${err.message}`;
      status.classList.add('is-error');
    } finally {
      button.disabled = false;
    }
  });

  loadMessages();
}

// ── Stage 3: uploads recorded by the S3 trigger ────────────────────────────

async function loadUploads() {
  const list = $('#upload-list');
  try {
    const { items } = await api('/uploads');
    if (items.length === 0) return showEmpty(list, 'Nothing yet. Upload a file to the uploads bucket.');
    list.replaceChildren(...items.map((f) => feedItem(f.key, `${(f.size / 1024).toFixed(1)} KB · ${timeAgo(f.at)}`)));
  } catch {
    showEmpty(list, 'Uploads are unavailable right now.');
  }
}

function initUploads() {
  loadUploads();
  // Refresh while the tab is visible, so the class sees the trigger fire live.
  setInterval(() => { if (!document.hidden) loadUploads(); }, UPLOAD_REFRESH_MS);
}

// ── Start ──────────────────────────────────────────────────────────────────

async function main() {
  $('#year').textContent = new Date().getFullYear();

  const config = await getConfig();
  const stage = Number(config.stage) || 1;

  if (config.deployedWith) $('#deploy-tag').textContent = `Hosted on AWS · deployed with ${config.deployedWith}`;
  markStagesLive(stage);

  if (stage >= 2) {
    showFeature('api');
    initVisits();
    initGuestbook();
  }
  if (stage >= 3) {
    showFeature('uploads');
    initUploads();
  }
}

main();
