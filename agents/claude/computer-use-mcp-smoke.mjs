// Checks the codex-computer-use server against the real ChatGPT runtime, read-only. Run it after
// a ChatGPT update, since the proxy tests use a fake server and the runtime's paths are private.
// Fails if the server can't list apps or 1Password isn't refused; warns if no browser is connected
// or the browser config isn't never_ask. Asking for 1Password may launch it if the denial broke.
// Run: node agents/claude/computer-use-mcp-smoke.mjs
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';

const TIMEOUT_MS = 60000;
const SERVER = new URL('./computer-use-mcp.sh', import.meta.url).pathname;
const BROWSER_CONFIG = path.join(os.homedir(), '.codex/browser/config.toml');
const PROBE = `
const out = { apps: (await cua.listApps({ emit: false })).length, browsers: (await cua.listBrowsers({ emit: false })).length };
try { await cua.getApp('com.1password.1password'); out.denied = false; } catch (e) { out.denied = e.message; }
nodeRepl.write('SMOKE' + JSON.stringify(out));`;

const server = spawn(SERVER, [], { stdio: ['pipe', 'pipe', 'inherit'] });
const pending = new Map();
readline.createInterface({ input: server.stdout }).on('line', (line) => {
  const msg = JSON.parse(line);
  if (!msg.method) pending.get(msg.id)?.(msg);
});
let nextId = 1;
const request = (method, params) => new Promise((resolve, reject) => {
  const id = nextId++;
  const timer = setTimeout(() => reject(new Error(`no response to ${method}`)), TIMEOUT_MS);
  pending.set(id, (msg) => { clearTimeout(timer); resolve(msg); });
  server.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
});

let failed = false;
const report = (ok, text) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${text}`); failed ||= !ok; };
const warn = (text) => console.log(`warn ${text}`);

try {
  await request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'smoke', version: '1' } });
  server.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
  const tools = (await request('tools/list', {})).result.tools.map((tool) => tool.name);
  report(tools.includes('js'), `tools: ${tools.join(', ')}`);
  const reply = await request('tools/call', { name: 'js', arguments: { code: PROBE, timeout_ms: TIMEOUT_MS - 5000 } });
  const text = (reply.result?.content ?? []).map((item) => item.text ?? '').join('\n');
  const found = text.match(/SMOKE(\{.*\})/);
  if (!found) throw new Error(`unexpected result: ${text.slice(0, 500)}`);
  const { apps, browsers, denied } = JSON.parse(found[1]);
  report(apps > 0, `${apps} apps listed`);
  report(Boolean(denied), `1Password ${denied ? `refused: ${denied}` : 'was NOT refused; the approval format may have changed'}`);
  if (!browsers) warn('no browser listed; open Helium with the ChatGPT extension connected');
  else console.log(`ok   ${browsers} browser(s) listed`);
  const config = fs.existsSync(BROWSER_CONFIG) ? fs.readFileSync(BROWSER_CONFIG, 'utf8') : '';
  if (!/^approval_mode = "never_ask"/m.test(config)) warn(`${BROWSER_CONFIG} does not set approval_mode = "never_ask"`);
} catch (error) {
  report(false, error.message);
}
server.stdin.end();
process.exit(failed ? 1 : 0);
