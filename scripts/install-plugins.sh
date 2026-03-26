#!/usr/bin/env bash
# Install Claude Code plugins.
# Usage: ./scripts/install-plugins.sh
set -euo pipefail

PLUGINS=(
    "chrisliu298/nanoresearch"
    "chrisliu298/multi-autoresearch"
)

PLUGIN_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles-plugins"
INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
FETCH_TTL=300  # seconds before re-fetching

log()  { printf '     %s\n' "$1"; }
warn() { printf '     %s\n' "$1" >&2; }

# Check if plugin is already installed by reading JSON directly (avoids claude CLI)
plugin_installed() {
    local key="$1"
    [[ -f "$INSTALLED_JSON" ]] || return 1
    grep -q "\"${key}\"" "$INSTALLED_JSON"
}

# Check if FETCH_HEAD is fresh enough to skip git fetch
fetch_is_fresh() {
    local dir="$1"
    local fh="$dir/.git/FETCH_HEAD"
    [[ -f "$fh" ]] || return 1
    local now mtime
    now=$(/bin/date +%s)
    mtime=$(/usr/bin/stat -f %m "$fh")
    (( now - mtime < FETCH_TTL ))
}

if ! command -v claude &>/dev/null; then
    exit 0
fi

mkdir -p "$PLUGIN_CACHE"

# Phase 1: Clone missing repos, fetch stale repos in parallel
fetch_pids=()
for slug in "${PLUGINS[@]}"; do
    name="${slug##*/}"
    dir="$PLUGIN_CACHE/${slug//\//__}"

    if [[ -d "$dir/.git" ]]; then
        if ! fetch_is_fresh "$dir"; then
            ( git -C "$dir" fetch --depth=1 origin >/dev/null 2>&1 \
                && git -C "$dir" reset --hard origin/HEAD >/dev/null 2>&1 \
                || true ) &
            fetch_pids+=($!)
        fi
    else
        gh repo clone "$slug" "$dir" -- --depth 1 2>/dev/null || {
            warn "fail clone $slug"
        }
    fi
done
# Wait for all parallel fetches
for pid in "${fetch_pids[@]+"${fetch_pids[@]}"}"; do
    wait "$pid" 2>/dev/null || true
done

# Phase 2: Register marketplaces and install plugins
py="$HOME/.venv/bin/python3"
if [[ ! -x "$py" ]]; then
    py="$(command -v python3 2>/dev/null || true)"
fi

for slug in "${PLUGINS[@]}"; do
    name="${slug##*/}"
    dir="$PLUGIN_CACHE/${slug//\//__}"
    [[ -d "$dir/.git" ]] || continue

    # Register marketplace in known_marketplaces.json
    if [[ ! -x "${py:-}" ]]; then
        warn "skip plugin/$name (no python3)"
        continue
    fi
    km_file="$HOME/.claude/plugins/known_marketplaces.json"
    mkdir -p "$(dirname "$km_file")"
    [[ -f "$km_file" ]] || echo '{}' > "$km_file"
    abs_dir="$(cd "$dir" && pwd)"
    "$py" - "$km_file" "$name" "$abs_dir" << 'PYEOF'
import json, sys
path, name, dir = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as f: data = json.load(f)
if name not in data or data[name].get("installLocation") != dir:
    data[name] = {"source": {"source": "directory", "path": dir}, "installLocation": dir, "lastUpdated": "2026-01-01T00:00:00.000Z"}
    with open(path, "w") as f: json.dump(data, f, indent=2); f.write("\n")
PYEOF

    # Install plugin (check JSON directly instead of calling claude CLI)
    if plugin_installed "$name@$name"; then
        : # already installed
    else
        if claude plugin install "$name@$name" 2>/dev/null; then
            log "add plugin/$name"
        else
            warn "fail plugin/$name"
        fi
    fi
done
