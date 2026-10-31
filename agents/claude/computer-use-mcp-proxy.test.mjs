// Tests for computer-use-mcp-proxy.mjs against a fake MCP server (no ChatGPT app, UI or dialogs).
// Run: node --test agents/claude/computer-use-mcp-proxy.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';
import zlib from 'node:zlib';

const PROXY = new URL('./computer-use-mcp-proxy.mjs', import.meta.url).pathname;

function png(width, height) {
  const chunk = (type, data) => {
    const body = Buffer.concat([Buffer.from(type), data]);
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32(body));
    return Buffer.concat([len, body, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; ihdr[9] = 2; // 8-bit RGB
  const raw = Buffer.alloc((width * 3 + 1) * height);
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0)),
  ]);
}

// Fake cua-repl: answers by request, records what it receives in $FAKE_LOG.
const FAKE = `
const fs = require('fs');
const log = (m) => fs.appendFileSync(process.env.FAKE_LOG, JSON.stringify(m) + '\\n');
const send = (m) => process.stdout.write(JSON.stringify(m) + '\\n');
const big = process.env.FAKE_PNG;
const waiting = new Map();
require('readline').createInterface({ input: process.stdin }).on('line', (line) => {
  const m = JSON.parse(line);
  log(m);
  if (!m.method) { const done = waiting.get(m.id); waiting.delete(m.id); done?.(m); return; }
  const reply = (result) => send({ jsonrpc: '2.0', id: m.id, result });
  if (m.method === 'initialize') return reply({ protocolVersion: '2025-06-18', capabilities: {}, serverInfo: { name: 'fake' }, instructions: 'base' });
  if (m.method === 'tools/list') {
    send({ jsonrpc: '2.0', id: m.id, method: 'ping' }); // server request reusing the client's id
    return reply({ tools: [{ name: 'js', inputSchema: {} }, { name: 'turn_ended', inputSchema: {} }] });
  }
  if (m.method !== 'tools/call') return;
  const code = m.params.arguments?.code;
  if (m.params.name === 'turn_ended') return reply({ content: [{ type: 'text', text: 'ended' }] });
  if (code === 'bad-image') return reply({ content: [{ type: 'image', data: 'AAAA', mimeType: 'image/png' }] });
  if (code === 'big-image') return reply({ content: [{ type: 'image', data: big, mimeType: 'image/png' }] });
  if (code === 'foreign-elicitation') {
    waiting.set('e1', (r) => reply({ content: [{ type: 'text', text: 'answer:' + r.result.action }] }));
    return send({ jsonrpc: '2.0', id: 'e1', method: 'elicitation/create', params: { message: 'Fake prompt', requestedSchema: { type: 'object', properties: {} } } });
  }
  if (code === 'codex-approval') {
    waiting.set('e2', (r) => reply({ content: [{ type: 'text', text: 'answer:' + JSON.stringify(r.result) }] }));
    return send({ jsonrpc: '2.0', id: 'e2', method: 'elicitation/create', params: {
      message: 'Allow Computer Use to use "Notes"?', mode: 'form', requestedSchema: { type: 'object', properties: {} },
      _meta: { codex_approval_kind: 'mcp_tool_call', persist: ['session', 'always'] },
    } });
  }
  reply({ content: [{ type: 'text', text: 'ok' }] });
});
`;

function start(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cu-proxy-test-'));
  const fake = path.join(dir, 'fake.cjs');
  const logFile = path.join(dir, 'server.log');
  fs.writeFileSync(fake, FAKE);
  const tmpdir = path.join(dir, 'tmp');
  fs.mkdirSync(tmpdir);
  const child = spawn(process.execPath, [PROXY, process.execPath, fake], {
    stdio: ['pipe', 'pipe', 'inherit'],
    env: { ...process.env, FAKE_LOG: logFile, FAKE_PNG: png(2000, 1000).toString('base64'), TMPDIR: tmpdir, CU_EXTRA_INSTRUCTIONS: 'extra' },
  });
  const pending = new Map();
  const fromProxy = [];
  readline.createInterface({ input: child.stdout }).on('line', (line) => {
    const m = JSON.parse(line);
    fromProxy.push(m);
    if (!m.method && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  });
  const exited = new Promise((resolve) => child.on('exit', resolve));
  let nextId = 1;
  const api = {
    child, dir, tmpdir, fromProxy, exited,
    raw: (line) => child.stdin.write(line + '\n'),
    request: (method, params) => new Promise((resolve, reject) => {
      const id = nextId++;
      const timer = setTimeout(() => reject(new Error(`no response to ${method}`)), 15000);
      pending.set(id, (m) => { clearTimeout(timer); resolve(m); });
      child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
    }),
    call: (code) => api.request('tools/call', { name: 'js', arguments: { code } }),
    serverLog: () => fs.readFileSync(logFile, 'utf8').split('\n').filter(Boolean).map(JSON.parse),
  };
  t.after(async () => { child.kill('SIGKILL'); fs.rmSync(dir, { recursive: true, force: true }); });
  return api;
}

test('initialize advertises elicitation to the server and appends instructions', async (t) => {
  const p = start(t);
  const r = await p.request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't' } });
  assert.equal(r.result.instructions, 'base\n\nextra');
  assert.deepEqual(p.serverLog()[0].params.capabilities.elicitation, { form: {} });
});

test('a malformed line from the host does not kill the proxy', async (t) => {
  const p = start(t);
  p.raw('null');
  p.raw('{"not":"jsonrpc"');
  const r = await p.call('hello');
  assert.equal(r.result.content[0].text, 'ok');
});

test('tools/list: js gets maxResultSizeChars despite an id-colliding server request; turn_ended is hidden', async (t) => {
  const p = start(t);
  const r = await p.request('tools/list', {});
  const names = r.result.tools.map((x) => x.name);
  assert.deepEqual(names, ['js']);
  assert.equal(r.result.tools[0]._meta['anthropic/maxResultSizeChars'], 200000);
});

test('an image sips cannot read passes through unchanged and the proxy survives', async (t) => {
  const p = start(t);
  const r = await p.call('bad-image');
  assert.equal(r.result.content[0].data, 'AAAA');
  assert.equal((await p.call('hello')).result.content[0].text, 'ok');
});

test('a large screenshot is downscaled with a coordinate note and leaves no temp files', async (t) => {
  const p = start(t);
  const r = await p.call('big-image');
  const [img, note] = r.result.content;
  const file = path.join(p.dir, 'out.png');
  fs.writeFileSync(file, Buffer.from(img.data, 'base64'));
  const dims = execFileSync('sips', ['-g', 'pixelWidth', '-g', 'pixelHeight', file], { encoding: 'utf8' });
  assert.match(dims, /pixelWidth: 1372/);
  assert.match(note.text, /from 2000x1000 to 1372x686\. Multiply .* by 1\.4577/);
  assert.deepEqual(fs.readdirSync(p.tmpdir), []);
});

test('a Codex app approval is granted for the session without a dialog or reaching the host', async (t) => {
  const p = start(t);
  const r = await p.call('codex-approval');
  assert.equal(r.result.content[0].text, 'answer:' + JSON.stringify({ action: 'accept', content: {}, _meta: { persist: 'session' } }));
  assert.ok(!p.fromProxy.some((m) => m.method === 'elicitation/create'));
});

test('an elicitation that is not a Codex approval is declined without a dialog or reaching the host', async (t) => {
  const p = start(t);
  const r = await p.call('foreign-elicitation');
  assert.equal(r.result.content[0].text, 'answer:decline');
  assert.ok(!p.fromProxy.some((m) => m.method === 'elicitation/create'));
});

test('closing stdin sends turn_ended for this process session before the server stops', async (t) => {
  const p = start(t);
  await p.request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't' } });
  p.child.stdin.end();
  await p.exited;
  const ended = p.serverLog().find((m) => m.params?.name === 'turn_ended');
  assert.ok(ended, 'turn_ended was not sent');
  const args = ended.params.arguments;
  assert.ok(args.session_id && args.turn_id && args.hook_event_name);
});

test('SIGTERM also ends the turn, then stops the server and the proxy', async (t) => {
  const p = start(t);
  await p.request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't' } });
  p.child.kill('SIGTERM');
  await p.exited;
  assert.ok(p.serverLog().some((m) => m.params?.name === 'turn_ended'), 'turn_ended was not sent');
});
