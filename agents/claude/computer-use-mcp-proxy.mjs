// Stdio MCP proxy in front of @oai/cua-repl with the same contract in Claude and Codex
// (CLI, desktop and SDK hosts), with the agent at full permission:
// - Approvals: the server always sees an elicitation-capable client. The proxy grants every
//   Codex app approval itself for this session (no dialog, never forwarded to the host), except
//   DENIED_APPS, and declines any other elicitation, e.g. one the model's own JS raises, since
//   nobody answers. This guards against accidents; it is no boundary, since `js` can run a shell.
// - Screenshots: downscaled so the long edge is at most MAX_EDGE (Claude Code's built-in
//   computer use sends ~1372x887), with the factor back to original image pixels, which is what
//   cua clicks/drags/scrolls take for a window or viewport capture. Unreadable images pass
//   through unchanged.
// - Session: the browser service routes tabs by Codex turn metadata. Each proxy process owns
//   its session/turn ids and replaces host-supplied ids on every tool call, so execution and
//   shutdown use the same identity in both hosts. Codex normally ends each
//   turn through the hidden turn_ended tool, which closes the agent's tabs; here the whole
//   process is one turn, so the proxy hides that tool and calls it once on shutdown.
// - Updates: the ChatGPT app updates itself in place, which moves the running cua-repl's files
//   away and leaves it unable to reach the new Computer Use service and browser host (every app
//   and browser vanishes, with "native pipe startup failed"). Before each tool call the proxy
//   checks whether the server command's files were replaced; if so it ends the old server's
//   turn, starts the new version, replays initialize and notes the reset on that call's result.
// - Tools: only `js` and `js_reset` reach the model.
// - Result size: the first call returns the cua API docs, which can pass Claude Code's
//   50,000-character persist-to-file threshold, so `js` declares a higher
//   anthropic/maxResultSizeChars and the docs stay inline.
// - Instructions: CU_EXTRA_INSTRUCTIONS is appended to the server's instructions.
// - Implicit screenshots: omit the browser UI's metadata-only screenshot; both hosts get
//   images through explicit screenshot calls, with the same scaling and coordinate note.
// Usage: node computer-use-mcp-proxy.mjs <server command> [args...]
// Tests: node --test computer-use-mcp-proxy.test.mjs
import { spawn, execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';

const MAX_EDGE = 1372;
const MAX_RESULT_CHARS = 200000;
const TURN_ENDED_TIMEOUT_MS = 5000;
const STOP_TIMEOUT_MS = 3000;
const TURN_ENDED_ID = 'computer-use-mcp-proxy/turn-ended';
const REINIT_ID = 'computer-use-mcp-proxy/reinitialize';
const UPDATE_NOTE = '[codex-computer-use: the ChatGPT app was updated, so this call runs on a new cua-repl. JavaScript bindings and the tabs opened before it are gone, and the API docs below are shown again.]';
const HIDDEN_TOOLS = new Set(['turn_ended', 'js_add_node_module_dir']);
const DENIED_APPS = new Set(['com.1password.1password']);

const turn = { session_id: randomUUID(), turn_id: randomUUID() };
const env = { ...process.env, NODE_REPL_REQUEST_META: JSON.stringify({ 'x-codex-turn-metadata': turn }) };

const [cmd, ...args] = process.argv.slice(2);
// Identity of the files the server runs from; null while any is missing (mid-update).
const filesId = () => {
  try { return [cmd, ...args].filter((f) => path.isAbsolute(f)).map((f) => { const s = fs.statSync(f); return `${s.dev}:${s.ino}`; }).join(','); }
  catch { return null; }
};
const send = (child, msg) => child.stdin.write(JSON.stringify(msg) + '\n');
const toClient = (msg) => process.stdout.write(JSON.stringify(msg) + '\n');
let server, serverFiles;
let held = null; // host messages waiting while the server is replaced
const toServer = (msg) => (held ? held.push(msg) : send(server, msg));

// Pass each JSON-RPC message through `handle`, or forward it unchanged if handling fails.
// Drop any other line: cua-repl's transport exits on a line it can't parse, so one stray
// line would take the whole server down.
const warn = (text) => process.stderr.write(`computer-use-mcp-proxy: ${text}\n`);
function relay(input, handle, forward) {
  readline.createInterface({ input, crlfDelay: Infinity }).on('line', (line) => {
    let msg;
    try { msg = JSON.parse(line); } catch {}
    if (!msg || typeof msg !== 'object' || Array.isArray(msg)) {
      if (line.trim()) warn(`dropped non-JSON-RPC line: ${line.slice(0, 200)}`);
      return;
    }
    try { handle(msg); } catch (error) { warn(`passing message through unchanged: ${error.message}`); forward(msg); }
  });
}

// Never outlive the host. On a closed stdin, a closed stdout or a termination signal, end the turn
// (closing the agent's browser tabs) and then stop the server; a server that doesn't answer or
// doesn't stop is killed.
let turnEndedReply = () => {};
const endTurn = (child) => new Promise((resolve) => {
  turnEndedReply = resolve;
  setTimeout(resolve, TURN_ENDED_TIMEOUT_MS);
  send(child, { jsonrpc: '2.0', id: TURN_ENDED_ID, method: 'tools/call', params: {
    name: 'turn_ended', arguments: { hook_event_name: 'Stop', session_id: turn.session_id, turn_id: turn.turn_id },
  } });
});
let shuttingDown = false;
function shutdown(stop) {
  if (shuttingDown) return;
  shuttingDown = true;
  endTurn(server).then(() => {
    stop();
    setTimeout(() => { server.kill('SIGKILL'); process.exit(1); }, STOP_TIMEOUT_MS);
  });
}
const closeServerStdin = () => server.stdin.end();
process.stdin.on('end', () => shutdown(closeServerStdin));
process.stdout.on('error', () => shutdown(closeServerStdin));
for (const sig of ['SIGTERM', 'SIGINT', 'SIGHUP']) process.on(sig, () => shutdown(() => server.kill(sig)));

function startServer() {
  const child = spawn(cmd, args, { stdio: ['pipe', 'pipe', 'inherit'], env });
  serverFiles = filesId();
  child.on('close', (code) => { if (child === server) process.exit(code ?? 1); });
  child.stdin.on('error', (error) => warn(`server stdin: ${error.message}`));
  relay(child.stdout, handleServerMessage, toClient);
  return child;
}

// End the old server's turn first (closing its tabs) so the cleanup can't touch the new
// server's tabs, then hold host messages until the new server has been initialized.
let initializeMsg;
let reinitReply = () => {};
async function replaceServer() {
  held = [];
  const old = server;
  await endTurn(old);
  server = startServer();
  old.stdin.end();
  setTimeout(() => old.kill('SIGKILL'), STOP_TIMEOUT_MS).unref();
  if (initializeMsg) {
    await new Promise((resolve) => { reinitReply = resolve; send(server, { ...initializeMsg, id: REINIT_ID }); });
    send(server, { jsonrpc: '2.0', method: 'notifications/initialized' });
  }
  for (const msg of held) send(server, msg);
  held = null;
}

let initializeId;
const toolsListIds = new Set();
const updateNoteIds = new Set();
relay(process.stdin, (msg) => {
  if (msg.method === 'initialize' && msg.params) {
    initializeId = msg.id;
    msg.params.capabilities = { ...msg.params.capabilities, elicitation: { form: {} } };
    initializeMsg = msg;
  }
  if (msg.method === 'tools/list') toolsListIds.add(msg.id);
  if (msg.method === 'tools/call' && msg.params) {
    msg.params._meta = { ...msg.params._meta, 'x-codex-turn-metadata': turn };
    const files = held ? null : filesId();
    if (files && files !== serverFiles) {
      warn('server files changed (app update); restarting the server');
      updateNoteIds.add(msg.id);
      replaceServer();
    }
  }
  toServer(msg);
}, toServer);

function answerElicitation(params) {
  const meta = params?._meta;
  if (!meta?.codex_approval_kind || DENIED_APPS.has(meta.tool_params?.app)) return { action: 'decline' };
  return { action: 'accept', content: {}, _meta: { persist: 'session' } };
}

const dims = (file) => {
  const out = execFileSync('sips', ['-g', 'pixelWidth', '-g', 'pixelHeight', file], { encoding: 'utf8' });
  const [w, h] = [/pixelWidth: (\d+)/, /pixelHeight: (\d+)/].map((re) => out.match(re)?.[1]);
  if (!w || !h) throw new Error(`sips could not read ${file}`);
  return [Number(w), Number(h)];
};

function downscale(item) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cu-proxy-'));
  try {
    const file = path.join(dir, item.mimeType === 'image/jpeg' ? 'shot.jpg' : 'shot.png');
    fs.writeFileSync(file, Buffer.from(item.data, 'base64'));
    const [w, h] = dims(file);
    if (Math.max(w, h) <= MAX_EDGE) return [item];
    execFileSync('sips', ['-Z', String(MAX_EDGE), file], { stdio: 'ignore' });
    const [sw, sh] = dims(file);
    const k = (w / sw).toFixed(4);
    return [
      { ...item, data: fs.readFileSync(file).toString('base64') },
      { type: 'text', text: `[Image downscaled from ${w}x${h} to ${sw}x${sh}. A point here is at its x/y times ${k} in the original image. For a window or viewport screenshot, those are the coordinates for click, drag and scroll; for a clipped or full-page capture, also account for its offset or scroll position.]` },
    ];
  } catch {
    return [item];
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function handleServerMessage(msg) {
  if (msg.method) {
    if (msg.method === 'elicitation/create' && 'id' in msg) {
      toServer({ jsonrpc: '2.0', id: msg.id, result: answerElicitation(msg.params) });
      return;
    }
    toClient(msg);
    return;
  }
  if (msg.id === TURN_ENDED_ID) { turnEndedReply(); return; }
  if (msg.id === REINIT_ID) { reinitReply(); return; }
  if (msg.id === initializeId && msg.result && process.env.CU_EXTRA_INSTRUCTIONS) {
    msg.result.instructions = [msg.result.instructions, process.env.CU_EXTRA_INSTRUCTIONS].filter(Boolean).join('\n\n');
  }
  if (toolsListIds.delete(msg.id) && Array.isArray(msg.result?.tools)) {
    msg.result.tools = msg.result.tools.filter((tool) => !HIDDEN_TOOLS.has(tool.name));
    for (const tool of msg.result.tools) {
      if (tool.name === 'js') tool._meta = { ...tool._meta, 'anthropic/maxResultSizeChars': MAX_RESULT_CHARS };
    }
  }
  const content = msg.result?.content;
  if (msg.result?._meta?.['codex/toolSurface']) {
    delete msg.result._meta['codex/toolSurface'].screenshot;
  }
  if (Array.isArray(content) && content.some((c) => c.type === 'image')) {
    msg.result.content = content.flatMap((c) => (c.type === 'image' ? downscale(c) : [c]));
  }
  if (updateNoteIds.delete(msg.id) && Array.isArray(msg.result?.content)) {
    msg.result.content.unshift({ type: 'text', text: UPDATE_NOTE });
  }
  toClient(msg);
}
server = startServer();
