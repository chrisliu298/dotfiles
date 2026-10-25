// Native Cursor session support: isolated configuration and explicit transcript completion.
import { createHash, randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync, renameSync, mkdirSync, realpathSync, rmSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

const [action, dir, workspace, conversation] = process.argv.slice(2);
function publish(name, value) {
  writeFileSync(join(dir, `${name}.tmp`), value);
  renameSync(join(dir, `${name}.tmp`), join(dir, name));
}
function snapshot() {
  const paths = JSON.parse(readFileSync(join(dir, 'transcript-paths.json'), 'utf8'));
  for (const path of paths) {
    try {
      const text = readFileSync(path, 'utf8');
      if (!text.endsWith('\n')) continue;
      return text.split('\n').filter(line => line.trim()).map(line => JSON.parse(line));
    } catch (error) {
      if (error.code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error;
    }
  }
  return [];
}
const textOf = record => (record.message?.content || [])
  .filter(block => block.type === 'text').map(block => block.text || '').join('');
const hash = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
// Cursor also writes user records of its own: steering continuations, bare timestamps,
// and background-task notices. Only requests start a reply or deliver a message.
const injected = /^(?:<timestamp>[^<]*<\/timestamp>\s*)?(?:Your previous response was interrupted\. Continue from where you left off\.|<user_query>Briefly inform the user about the task result and perform any follow-up actions \(if needed\)\.<\/user_query>)?\s*$/;
const isRequest = record => record.role === 'user' && !injected.test(textOf(record));
function userKey(records) {
  const index = records.findLastIndex(isRequest);
  return index < 0 ? null : hash([index, records[index]]);
}
function received(records, expected) {
  const user = records.findLast(isRequest);
  return userKey(records) !== expected.userKey && textOf(user || {}).includes(expected.text);
}

if (action === 'config') {
  const original = process.env.CURSOR_CONFIG_DIR ||
    (process.env.XDG_CONFIG_HOME ? join(process.env.XDG_CONFIG_HOME, 'cursor') : join(homedir(), '.cursor'));
  let config = {};
  try { config = JSON.parse(readFileSync(join(original, 'cli-config.json'), 'utf8')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  config.steering = true;
  config.modelSlashCommands = false;
  config.permissions ||= {};
  config.permissions.allow = [...new Set([
    ...(config.permissions.allow || []), 'Read(**)', 'Write(**)', 'Shell(*)', 'Mcp(*:*)', 'WebFetch(*)',
  ])];
  config.permissions.deny = [];
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  writeFileSync(join(dir, 'cli-config.json'), JSON.stringify(config), { mode: 0o600 });
} else if (action === 'paths') {
  const slug = realpathSync(workspace).replace(/[^a-zA-Z0-9]/g, '-').replace(/-+/g, '-').replace(/^-+|-+$/g, '');
  const base = join(process.env.CURSOR_DATA_DIR || join(homedir(), '.cursor'),
    'projects', slug, 'agent-transcripts');
  publish('transcript-paths.json', JSON.stringify([
    join(base, conversation, `${conversation}.jsonl`), join(base, `${conversation}.jsonl`),
  ]));
} else if (action === 'mark-send') {
  const text = readFileSync(workspace, 'utf8').trimEnd();
  publish('latest-message.json', JSON.stringify({ id: randomUUID(), text, userKey: userKey(snapshot()) }));
} else if (action === 'received') {
  let expected;
  try { expected = JSON.parse(readFileSync(join(dir, 'latest-message.json'), 'utf8')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  // A removed marker means the watcher already saw this message finish.
  process.exit(!expected || received(snapshot(), expected) ? 0 : 1);
} else if (action === 'watch') {
  let done = 0, undelivered = null;
  const seen = new Set();
  // Cursor submits a message that missed a failed turn as a follow-up within seconds, if at all.
  const grace = Number(process.env.AGENT_TEAM_CURSOR_UNDELIVERED_MS || 30000);
  const failure = record => `Cursor turn ${record.status || 'ended without status'}${record.error ? `: ${record.error}` : ''}`;
  const pending = () => {
    try { return JSON.parse(readFileSync(join(dir, 'latest-message.json'), 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  };
  function poll() {
    const records = snapshot();
    const prefix = [], replies = [];
    for (const record of records) {
      if (record.type !== 'turn_ended') {
        prefix.push(record);
        if (isRequest(record)) replies.length = 0;
        if (record.role === 'assistant' && textOf(record).trim()) replies.push(textOf(record));
        continue;
      }
      const key = hash([prefix, record]);
      if (seen.has(key)) continue;
      const expected = pending();
      seen.add(key);
      if (expected && !received(prefix, expected)) {
        // The turn ended before the latest message joined it, so it never answers that message.
        if (record.status !== 'success') undelivered = { id: expected.id, since: Date.now(), error: failure(record) };
        continue;
      }
      if (record.status !== 'success' || replies.length === 0) {
        publish('error', `${failure(record)}${replies.length ? '' : ' without a complete response'}`);
        // Text written before the failure may be complete, but nothing proves it.
        if (replies.length) publish('partial', replies.join('\n\n'));
        else rmSync(join(dir, 'partial'), { force: true });
      } else {
        publish('last', replies.join('\n\n'));
        rmSync(join(dir, 'error'), { force: true });
        rmSync(join(dir, 'partial'), { force: true });
        publish('done', String(++done));
      }
      if (expected) {
        const current = JSON.parse(readFileSync(join(dir, 'latest-message.json'), 'utf8'));
        if (current.id === expected.id) rmSync(join(dir, 'latest-message.json'), { force: true });
      }
    }
    if (undelivered) {
      const current = pending();
      if (!current || current.id !== undelivered.id || received(records, current)) undelivered = null;
      else if (Date.now() - undelivered.since >= grace) {
        // The marker stays: `wait` must not resume the turn and silently drop the message.
        publish('error', `${undelivered.error} before the latest message joined the turn; it was not delivered, so resending it is safe`);
        undelivered = null;
      }
    }
  }
  const timer = setInterval(() => {
    try { poll(); } catch (error) { publish('error', `Cursor transcript tracker failed: ${error.message}`); }
  }, 100);
  for (const signal of ['SIGTERM', 'SIGHUP', 'SIGINT']) process.on(signal, () => { clearInterval(timer); process.exit(0); });
} else {
  throw new Error('usage: cursor-session.mjs config|paths|mark-send|received|watch DIR [WORKSPACE|MESSAGE_FILE] [CONVERSATION]');
}
