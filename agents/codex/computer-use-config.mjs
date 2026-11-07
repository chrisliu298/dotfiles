// Reconcile the shared Computer Use entrypoint using Codex's own TOML reader/writer.
// Run: node agents/codex/computer-use-config.mjs
// Tests: node --test agents/codex/computer-use-config.test.mjs (isolated CODEX_HOME).
import { spawn } from 'node:child_process';
import { isDeepStrictEqual } from 'node:util';
import os from 'node:os';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';

const launcher = fileURLToPath(new URL('../claude/computer-use-mcp.sh', import.meta.url));
const child = spawn('codex', ['app-server', '--stdio'], {
  cwd: process.env.CODEX_HOME || os.homedir(), stdio: ['pipe', 'pipe', 'inherit'],
});
const pending = new Map();
let nextId = 1;
function failPending(error) {
  for (const { reject } of pending.values()) reject(error);
  pending.clear();
}
child.on('error', failPending);
child.on('exit', (code) => failPending(new Error(`Codex app-server exited (${code})`)));
readline.createInterface({ input: child.stdout }).on('line', (line) => {
  const msg = JSON.parse(line);
  const request = pending.get(msg.id);
  if (!request) return;
  pending.delete(msg.id);
  if (msg.error) request.reject(new Error(msg.error.message));
  else request.resolve(msg.result);
});
function rpc(method, params) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`Codex ${method} timed out`));
    }, 30000);
    pending.set(id, {
      resolve: (value) => { clearTimeout(timer); resolve(value); },
      reject: (error) => { clearTimeout(timer); reject(error); },
    });
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  });
}

try {
  await rpc('initialize', { clientInfo: { name: 'dotfiles-computer-use', version: '1' } });
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'initialized' }) + '\n');
  const before = await rpc('config/read', { includeLayers: true });
  const user = before.layers?.find((layer) => layer.name.type === 'user');
  const config = user?.config || {};
  const desired = [];
  const set = (keys, value) => desired.push({ keys, value });
  for (const name of ['unified-computer-use', 'computer-use', 'chrome', 'browser']) {
    set(['plugins', `${name}@openai-bundled`, 'enabled'], false);
  }
  // Keep generic node_repl for non-UI work; its browser plugins are disabled above.
  for (const name of ['computer-use', 'chrome-devtools']) {
    if (config.mcp_servers?.[name]) set(['mcp_servers', name, 'enabled'], false);
  }
  for (const [key, value] of Object.entries({
    command: launcher, args: [], enabled: true, enabled_tools: ['js', 'js_reset'],
    disabled_tools: [], startup_timeout_sec: 120, tool_timeout_sec: 60,
  })) set(['mcp_servers', 'codex-computer-use', key], value);
  // Match the native runtime's budget: first-use/reset documentation can exceed default limits.
  set(['mcp_servers', 'codex-computer-use', 'tools', 'js', 'output_token_limit'], 25000);
  const valueAt = (object, keys) => keys.reduce((value, key) => value?.[key], object);
  const edits = desired.filter(({ keys, value }) => !isDeepStrictEqual(valueAt(config, keys), value))
    .map(({ keys, value }) => ({ keyPath: keys.join('.'), value, mergeStrategy: 'replace' }));
  if (edits.length) {
    await rpc('config/batchWrite', { edits, expectedVersion: user?.version, reloadUserConfig: false });
  }
  const after = (await rpc('config/read', { includeLayers: false })).config;
  for (const { keys, value } of desired) {
    if (!isDeepStrictEqual(valueAt(after, keys), value)) throw new Error(`Config did not take effect: ${keys.join('.')}`);
  }
  console.log(`Codex Computer Use: ${edits.length ? 'configured shared MCP; restart existing sessions' : 'already configured'}`);
} catch (error) {
  console.error(`Codex Computer Use: ${error.message}`);
  process.exitCode = 1;
} finally {
  child.stdin.end();
  setTimeout(() => child.kill('SIGTERM'), 3000).unref();
}
