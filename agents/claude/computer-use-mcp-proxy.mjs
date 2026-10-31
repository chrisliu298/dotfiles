// Stdio MCP proxy in front of @oai/cua-repl that makes it behave the same in every Claude host
// (CLI, T3 Code, Agent SDK apps), with the agent at full permission:
// - Approvals: the server always sees an elicitation-capable client. The proxy grants every
//   Codex app approval itself for this session (no dialog, never forwarded to the host), except
//   DENIED_APPS, and declines any other elicitation, e.g. one the model's own JS raises, since
//   nobody answers. This guards against accidents; it is no boundary, since `js` can run a shell.
// - Screenshots: downscaled so the long edge is at most MAX_EDGE (Claude Code's built-in
//   computer use sends ~1372x887), with the factor the model must multiply coordinates by,
//   since cua clicks/drags/scrolls take original screenshot pixels. Unreadable images pass
//   through unchanged.
// - Session: the browser service routes tabs by the Codex turn metadata, which Claude hosts
//   never send, so each proxy process supplies its own session/turn ids as the default
//   request metadata; concurrent Claude sessions then keep separate tabs. Codex ends each
//   turn through the hidden turn_ended tool, which closes the agent's tabs; here the whole
//   process is one turn, so the proxy hides that tool and calls it once on shutdown.
// - Tools: only `js` and `js_reset` reach the model.
// - Result size: the first call returns the cua API docs, which can pass Claude Code's
//   50,000-character persist-to-file threshold, so `js` declares a higher
//   anthropic/maxResultSizeChars and the docs stay inline.
// - Instructions: CU_EXTRA_INSTRUCTIONS is appended to the server's instructions.
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
const TURN_ENDED_ID = 'computer-use-mcp-proxy/turn-ended';
const HIDDEN_TOOLS = new Set(['turn_ended', 'js_add_node_module_dir']);
const DENIED_APPS = new Set(['com.1password.1password']);

const turn = { session_id: randomUUID(), turn_id: randomUUID() };
const env = { ...process.env, NODE_REPL_REQUEST_META: JSON.stringify({ 'x-codex-turn-metadata': turn }) };

const [cmd, ...args] = process.argv.slice(2);
const server = spawn(cmd, args, { stdio: ['pipe', 'pipe', 'inherit'], env });
server.on('close', (code) => process.exit(code ?? 1));
const toServer = (msg) => server.stdin.write(JSON.stringify(msg) + '\n');
const toClient = (msg) => process.stdout.write(JSON.stringify(msg) + '\n');

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

// Never outlive the host. On a closed stdin or a termination signal, end the turn (closing the
// agent's browser tabs) and then stop the server; a server that doesn't answer still stops.
let ended;
function shutdown(stop) {
  ended ??= new Promise((resolve) => {
    turnEndedReply = resolve;
    setTimeout(resolve, TURN_ENDED_TIMEOUT_MS);
    toServer({ jsonrpc: '2.0', id: TURN_ENDED_ID, method: 'tools/call', params: {
      name: 'turn_ended', arguments: { hook_event_name: 'Stop', session_id: turn.session_id, turn_id: turn.turn_id },
    } });
  });
  ended.then(stop);
}
let turnEndedReply = () => {};
process.stdin.on('end', () => shutdown(() => server.stdin.end()));
for (const sig of ['SIGTERM', 'SIGINT', 'SIGHUP']) process.on(sig, () => shutdown(() => server.kill(sig)));

let initializeId;
const toolsListIds = new Set();
relay(process.stdin, (msg) => {
  if (msg.method === 'initialize' && msg.params) {
    initializeId = msg.id;
    msg.params.capabilities = { ...msg.params.capabilities, elicitation: { form: {} } };
  }
  if (msg.method === 'tools/list') toolsListIds.add(msg.id);
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
      { type: 'text', text: `[Screenshot downscaled from ${w}x${h} to ${sw}x${sh}. Multiply x/y coordinates read from this image by ${k} before passing them to click, drag or scroll.]` },
    ];
  } catch {
    return [item];
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

relay(server.stdout, (msg) => {
  if (msg.method) {
    if (msg.method === 'elicitation/create' && 'id' in msg) {
      toServer({ jsonrpc: '2.0', id: msg.id, result: answerElicitation(msg.params) });
      return;
    }
    toClient(msg);
    return;
  }
  if (msg.id === TURN_ENDED_ID) { turnEndedReply(); return; }
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
  if (Array.isArray(content) && content.some((c) => c.type === 'image')) {
    msg.result.content = content.flatMap((c) => (c.type === 'image' ? downscale(c) : [c]));
  }
  toClient(msg);
}, toClient);
