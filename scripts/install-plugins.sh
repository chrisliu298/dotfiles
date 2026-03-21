#!/usr/bin/env bash
# Install Claude Code plugins.
# Usage: ./scripts/install-plugins.sh
set -euo pipefail

PLUGINS=(
    "chrisliu298/nanoresearch"
)

PLUGIN_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles-plugins"

log()  { printf '  %s\n' "$1"; }
warn() { printf '  ⚠ %s\n' "$1" >&2; }

if ! command -v claude &>/dev/null; then
    warn "claude CLI not found"
    exit 0
fi

printf '\n  Install Claude plugins\n\n'

mkdir -p "$PLUGIN_CACHE"

for slug in "${PLUGINS[@]}"; do
    name="${slug##*/}"
    dir="$PLUGIN_CACHE/${slug//\//__}"

    # Clone or update (use gh for private repo auth)
    if [[ -d "$dir/.git" ]]; then
        git -C "$dir" fetch --depth=1 origin >/dev/null 2>&1 \
            && git -C "$dir" reset --hard origin/HEAD >/dev/null 2>&1 \
            || true
    else
        gh repo clone "$slug" "$dir" -- --depth 1 2>/dev/null || {
            warn "fail clone $slug"; continue
        }
    fi

    # Register marketplace in known_marketplaces.json
    km_file="$HOME/.claude/plugins/known_marketplaces.json"
    mkdir -p "$(dirname "$km_file")"
    [[ -f "$km_file" ]] || echo '{}' > "$km_file"
    abs_dir="$(cd "$dir" && pwd)"
    "$HOME/.venv/bin/python3" - "$km_file" "$name" "$abs_dir" << 'PYEOF'
import json, sys
path, name, dir = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as f: data = json.load(f)
if name not in data or data[name].get("installLocation") != dir:
    data[name] = {"source": {"source": "directory", "path": dir}, "installLocation": dir, "lastUpdated": "2026-01-01T00:00:00.000Z"}
    with open(path, "w") as f: json.dump(data, f, indent=2); f.write("\n")
PYEOF

    # Install plugin
    if claude plugin list 2>/dev/null | grep -q "$name@$name"; then
        : # already installed
    else
        if claude plugin install "$name@$name" 2>/dev/null; then
            log "add plugin/$name"
        else
            warn "fail plugin/$name"
        fi
    fi
done

printf '\n  Done.\n'
