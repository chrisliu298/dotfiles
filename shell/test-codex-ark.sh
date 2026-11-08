#!/bin/sh
# Offline route checks; no credentials or model calls are used.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT HUP INT TERM
export XDG_CACHE_HOME="$scratch/cache" CODEX_ARK_CODEX_BIN="$scratch/codex"
export ARC_API_KEY=test-only ARK_OPERATOR_ID=test-operator ARK_OPERATOR_EMAIL=test@example.invalid
export ARK_SESSION_ID=route-test CAPTURE="$scratch/launch.json"
cat > "$CODEX_ARK_CODEX_BIN" <<'JS'
#!/usr/bin/env node
const fs = require('node:fs');
const args = process.argv.slice(2);
if (args[0] === 'debug') {
  if (JSON.stringify(args) !== JSON.stringify(['debug', 'models', '--bundled'])) process.exit(3);
  console.log(JSON.stringify({models: [{slug: 'gpt-6-astra', display_name: 'Astra',
    context_window: 272000, test_metadata: 'preserved'},
    {slug: 'gpt-6.1-sol', display_name: 'Sol', context_window: 272000,
    test_metadata: 'sol-preserved'}]}));
} else {
  const url = args.find(arg => arg.startsWith('model_providers.ark.base_url='));
  const port = Number(/127\.0\.0\.1:(\d+)\//.exec(url)?.[1]);
  // The relay is already listening when Codex starts.
  require('node:net').connect(port, '127.0.0.1')
    .on('connect', function () {
      this.destroy();
      fs.writeFileSync(process.env.CAPTURE, JSON.stringify({args, pid: process.pid,
        no_proxy: process.env.no_proxy, NO_PROXY: process.env.NO_PROXY}));
    })
    .on('error', () => process.exit(4));
}
JS
chmod +x "$CODEX_ARK_CODEX_BIN"
NO_PROXY=existing.invalid no_proxy=lower.invalid "$root/codex-ark" exec 'Reply OK'
node - "$CAPTURE" "$XDG_CACHE_HOME/codex-ark/models.json" <<'JS'
const assert = require('node:assert/strict');
const fs = require('node:fs');
const launch = JSON.parse(fs.readFileSync(process.argv[2]));
const catalog = JSON.parse(fs.readFileSync(process.argv[3]));
assert(launch.args.includes('--no-daemon'));
assert(launch.args.includes('model_provider="ark"'));
assert(launch.args.includes('model_providers.ark.env_key="ARC_API_KEY"'));
assert(launch.args.some(arg => /^model_providers\.ark\.base_url="http:\/\/127\.0\.0\.1:\d+\/api\/v3"$/.test(arg)));
assert(launch.args.includes('model_providers.ark.requires_openai_auth=false'));
assert(!launch.args.some(arg => arg.startsWith('model_reasoning_effort=')));
assert(launch.args.includes(`model_providers.ark.http_headers={"extra"='{"session_id":"route-test"}'}`));
assert.deepEqual(launch.args.slice(-3), ['ep-20261020213556-cxb6v', 'exec', 'Reply OK']);
assert.equal(launch.NO_PROXY, 'existing.invalid,127.0.0.1,ark-cn-beijing.bytedance.net');
assert.equal(launch.no_proxy, 'lower.invalid,127.0.0.1,ark-cn-beijing.bytedance.net');
assert.equal(catalog.models.length, 4);
assert.equal(catalog.models.find(m => m.slug === 'ep-20261020213556-cxb6v').test_metadata, 'preserved');
assert.equal(catalog.models.find(m => m.slug === 'ep-20261026202616-6c8l8').test_metadata, 'sol-preserved');
JS
# The relay ends with the Codex process that replaced codex-ark.
pid=$(node -p 'JSON.parse(require("node:fs").readFileSync(process.argv[1])).pid' "$CAPTURE")
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  LC_ALL=C pgrep -f "codex-ark-relay $pid " >/dev/null || break
  sleep 0.2
done
if LC_ALL=C pgrep -f "codex-ark-relay $pid " >/dev/null; then
  echo 'relay outlived Codex' >&2; exit 1
fi
for model in sol gpt-6.1-sol gpt-6-1-sol azure-gpt-6-1-sol ep-20261026202616-6c8l8; do
  ARK_MODEL="$model" "$root/codex-ark" resume --last
  node - "$CAPTURE" <<'JS'
const assert = require('node:assert/strict');
const launch = JSON.parse(require('node:fs').readFileSync(process.argv[2]));
assert.deepEqual(launch.args.slice(-3), ['ep-20261026202616-6c8l8', 'resume', '--last']);
assert(!launch.args.some(arg => arg.startsWith('model_reasoning_effort=')));
assert(launch.args.includes('model_provider="ark"'));
JS
done
rm "$CAPTURE"
if ARK_MODEL=unknown "$root/codex-ark" exec 'Reply OK' >"$scratch/out" 2>&1; then
  echo 'unknown Ark model unexpectedly accepted' >&2; exit 1
fi
test ! -e "$CAPTURE"
if ARC_API_KEY= "$root/codex-ark" exec 'Reply OK' >"$scratch/out" 2>&1; then
  echo 'missing key unexpectedly accepted' >&2; exit 1
fi
test ! -e "$CAPTURE"
grep -q 'ARC_API_KEY is not set' "$scratch/out"
if "$root/codex-ark" --model subscription-model >"$scratch/out" 2>&1; then
  echo 'model override unexpectedly accepted' >&2; exit 1
fi
test ! -e "$CAPTURE"
reject_override() {
  rm -f "$CAPTURE"
  if "$root/codex-ark" "$@" >"$scratch/out" 2>&1; then
    echo 'route override unexpectedly accepted' >&2; exit 1
  fi
  test ! -e "$CAPTURE"
}
reject_override --config='model_provider="openai"'
reject_override '-cmodel_provider="openai"'
reject_override -c 'model_provider = "openai"'
reject_override --config='model_providers.ark.base_url="https://example.invalid"'
"$root/codex-ark" exec 'model= is ordinary prompt text' --config='model_reasoning_effort="high"'
node - "$CAPTURE" <<'JS'
const assert = require('node:assert/strict');
const launch = JSON.parse(require('node:fs').readFileSync(process.argv[2]));
assert(launch.args.includes('model= is ordinary prompt text'));
assert(launch.args.includes('--config=model_reasoning_effort="high"'));
JS
node - "$root/.functions" "$scratch/ark-aliases.zsh" <<'JS'
const fs = require('node:fs');
const aliases = fs.readFileSync(process.argv[2], 'utf8').split('\n')
  .filter(line => /^xas(?:c|r)?\(\)/.test(line));
if (aliases.length !== 3) throw Error('missing Ark Sol aliases');
fs.writeFileSync(process.argv[3], aliases.join('\n') + '\n');
JS
for invocation in "xas exec alias-check" "xasc" "xasr session-check"; do
  PATH="$root:$PATH" zsh -fc 'source "$1"; eval "$2"' route-test "$scratch/ark-aliases.zsh" "$invocation"
  node - "$CAPTURE" "$invocation" <<'JS'
const assert = require('node:assert/strict');
const launch = JSON.parse(require('node:fs').readFileSync(process.argv[2]));
const suffix = { 'xas exec alias-check': ['--yolo', 'exec', 'alias-check'],
  xasc: ['--yolo', 'resume', '--last'],
  'xasr session-check': ['--yolo', 'resume', 'session-check'] }[process.argv[3]];
assert.deepEqual(launch.args.slice(-(suffix.length + 1)), ['ep-20261026202616-6c8l8', ...suffix]);
JS
done
# Relay behavior against a local stand-in for Ark (Retry-After: 0 keeps the retries instant).
node - "$root/codex-ark-relay" <<'JS'
const assert = require('node:assert/strict');
const http = require('node:http');
const { spawn } = require('node:child_process');
const seen = [];
let script = [];
let after = '0';
const ark = http.createServer((req, res) => {
  let body = '';
  req.on('data', chunk => { body += chunk; }).on('end', () => {
    seen.push({ url: req.url, body, auth: req.headers.authorization, host: req.headers.host });
    const status = script.shift() ?? 200;
    if (status === 429) return res.writeHead(429, { 'retry-after': after }).end('{"error":"rate"}');
    if (status !== 200) return res.writeHead(status).end('broken');
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    res.write('data: one\n\n');
    setTimeout(() => res.end('data: two\n\n'), 50);
  });
});
const post = (port, body) => new Promise((resolve, reject) => {
  http.request({ port, host: '127.0.0.1', method: 'POST', path: '/api/v3/responses',
    headers: { authorization: 'Bearer test', 'content-type': 'application/json' } }, res => {
    let text = '';
    res.on('data', chunk => { text += chunk; }).on('end', () => resolve({ status: res.statusCode, text }));
  }).on('error', reject).end(body);
});
ark.listen(0, '127.0.0.1', async () => {
  const relay = spawn(process.execPath, [process.argv[2], String(process.pid),
    `http://127.0.0.1:${ark.address().port}`], { stdio: ['ignore', 'pipe', 'pipe'] });
  let log = '';
  relay.stderr.on('data', chunk => { log += chunk; });
  const port = Number(await new Promise(resolve => relay.stdout.once('data', resolve)));

  script = [429, 429, 200];
  assert.deepEqual(await post(port, '{"n":1}'), { status: 200, text: 'data: one\n\ndata: two\n\n' });
  assert.equal(seen.length, 3);
  assert(seen.every(r => r.body === '{"n":1}' && r.auth === 'Bearer test' &&
    r.url === '/api/v3/responses' && r.host === `127.0.0.1:${ark.address().port}`));
  assert.match(log, /retry 2 in/);

  // No retry limit: 40 rate limits in a row still end in the reply.
  seen.length = 0; script = [...Array(40).fill(429), 200];
  assert.equal((await post(port, '{}')).status, 200);
  assert.equal(seen.length, 41);

  // A request Codex drops (an interrupt) stops retrying instead of running on forever.
  seen.length = 0; script = Array(40).fill(429); after = '1';
  const dropped = http.request({ port, host: '127.0.0.1', method: 'POST', path: '/api/v3/responses' });
  dropped.on('error', () => {}).end('{}');
  while (!seen.length) await new Promise(resolve => setTimeout(resolve, 10));
  dropped.destroy();
  await new Promise(resolve => setTimeout(resolve, 300));
  assert.equal(seen.length, 1);
  assert.match(log, /dropped by Codex while waiting/);
  after = '0';

  seen.length = 0; script = [500];
  assert.deepEqual(await post(port, '{}'), { status: 500, text: 'broken' });
  assert.equal(seen.length, 1);

  relay.kill(); ark.close();
});
JS
echo 'codex-ark offline route checks passed'
