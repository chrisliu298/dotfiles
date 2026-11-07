// Uses the installed Codex parser/writer with an isolated CODEX_HOME; no model or UI calls.
// Run: node --test agents/codex/computer-use-config.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('./computer-use-config.mjs', import.meta.url));

test('Codex migration preserves unrelated config and generic JS, and is idempotent', (t) => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-cu-config-'));
  t.after(() => fs.rmSync(home, { recursive: true, force: true }));
  const config = path.join(home, 'config.toml');
  fs.writeFileSync(config, `# keep this comment\nmodel = "gpt-6.1-sol"\n[mcp_servers.node_repl]\ncommand = "node"\nenabled = true\n[mcp_servers.chrome-devtools]\ncommand = "npx"\nenabled = true\n[plugins."chrome@openai-bundled"]\nenabled = true\n[plugins."unrelated@example"]\nenabled = true\n`);
  const run = () => execFileSync(process.execPath, [script], {
    env: { ...process.env, CODEX_HOME: home }, encoding: 'utf8', timeout: 45000,
  });
  run();
  const installed = fs.readFileSync(config, 'utf8');
  assert.match(installed, /# keep this comment/);
  assert.match(installed, /model = "gpt-6\.1-sol"/);
  assert.match(installed, /\[mcp_servers.node_repl\]\ncommand = "node"\nenabled = true/);
  assert.match(installed, /\[plugins\."unrelated@example"\]\nenabled = true/);
  assert.match(installed, /\[mcp_servers.chrome-devtools\]\ncommand = "npx"\nenabled = false/);
  for (const name of ['chrome', 'browser', 'computer-use', 'unified-computer-use']) {
    assert.ok(installed.includes(`[plugins."${name}@openai-bundled"]\nenabled = false`));
  }
  const mcp = JSON.parse(execFileSync('codex', ['mcp', 'get', 'codex-computer-use', '--json'], {
    env: { ...process.env, CODEX_HOME: home }, encoding: 'utf8', timeout: 15000,
  }));
  assert.equal(mcp.enabled, true);
  assert.equal(mcp.transport.command, fileURLToPath(new URL('../claude/computer-use-mcp.sh', import.meta.url)));
  assert.deepEqual(mcp.enabled_tools, ['js', 'js_reset']);
  assert.match(installed, /\[mcp_servers.codex-computer-use.tools.js\]\noutput_token_limit = 25000/);
  assert.match(run(), /already configured/);
  assert.equal(fs.readFileSync(config, 'utf8'), installed);
});
