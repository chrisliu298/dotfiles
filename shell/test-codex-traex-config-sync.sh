#!/bin/sh

set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/codex-traex-config-sync.XXXXXX")
trap 'rm -rf "$test_root"' EXIT HUP INT TERM

mkdir -p "$test_root/codex" "$test_root/codex-traex"

cat > "$test_root/codex/config.toml" <<EOF
model_reasoning_effort = "high"
model_verbosity = "low"
model = "gpt-6.1-sol"
approval_policy = "on-request"

[projects."$HOME"]
trust_level = "trusted"

[projects."/tmp/example"]
trust_level = "trusted"

[tui]
theme = "openai-dark"
EOF

cat > "$test_root/codex-traex/config.toml" <<'EOF'
model = "GPT-5.6-Sol"
model_reasoning_effort = "medium"
EOF

CODEX_TRAEX_HOME="$test_root/codex-traex" \
CODEX_TRAEX_SOURCE_CONFIG="$test_root/codex/config.toml" \
  "$repo_root/shell/codex-traex" sync-config

sed "s|HOME_PLACEHOLDER|$HOME|" <<'EOF' |
model_reasoning_effort = "high"
model_verbosity = "low"
model = "GPT-5.6-Sol"
approval_policy = "on-request"

[projects."HOME_PLACEHOLDER"]
trust_level = "untrusted"

[projects."/tmp/example"]
trust_level = "trusted"

[tui]
theme = "openai-dark"
EOF
  diff -u - "$test_root/codex-traex/config.toml"

grep -q '^model = "gpt-6.1-sol"$' "$test_root/codex/config.toml"

rm "$test_root/codex-traex/config.toml"
CODEX_TRAEX_HOME="$test_root/codex-traex" \
CODEX_TRAEX_SOURCE_CONFIG="$test_root/codex/config.toml" \
CODEX_TRAEX_DEFAULT_MODEL="GPT-5.6-Terra" \
  "$repo_root/shell/codex-traex" sync-config

grep -q '^model = "GPT-5.6-Terra"$' "$test_root/codex-traex/config.toml"
test "$(LC_ALL=C ls -l "$test_root/codex-traex/config.toml" | awk '{ print $1 }')" = "-rw-------"

CODEX_TRAEX_HOME="$test_root/codex-traex" \
CODEX_TRAEX_SOURCE_CONFIG="$test_root/missing.toml" \
  "$repo_root/shell/codex-traex" sync-config

grep -q '^model_verbosity = "low"$' "$test_root/codex-traex/config.toml"
