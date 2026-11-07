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
  fs.writeFileSync(process.env.CAPTURE, JSON.stringify({args,
    no_proxy: process.env.no_proxy, NO_PROXY: process.env.NO_PROXY}));
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
assert(launch.args.includes('model_providers.ark.base_url="https://ark-cn-beijing.bytedance.net/api/v3"'));
assert(launch.args.includes('model_providers.ark.requires_openai_auth=false'));
assert(!launch.args.some(arg => arg.startsWith('model_reasoning_effort=')));
assert(launch.args.includes(`model_providers.ark.http_headers={"extra"='{"session_id":"route-test"}'}`));
assert.deepEqual(launch.args.slice(-3), ['ep-20261020213556-cxb6v', 'exec', 'Reply OK']);
assert.equal(launch.NO_PROXY, 'existing.invalid,ark-cn-beijing.bytedance.net');
assert.equal(launch.no_proxy, 'lower.invalid,ark-cn-beijing.bytedance.net');
assert.equal(catalog.models.length, 4);
assert.equal(catalog.models.find(m => m.slug === 'ep-20261020213556-cxb6v').test_metadata, 'preserved');
assert.equal(catalog.models.find(m => m.slug === 'ep-20261026202616-6c8l8').test_metadata, 'sol-preserved');
JS
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
echo 'codex-ark offline route checks passed'
