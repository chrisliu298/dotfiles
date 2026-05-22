#!/usr/bin/env bash
# Install Claude Code plugins.
set -euo pipefail

PLUGINS=(
    chrisliu298/humanize
)
[[ ${#PLUGINS[@]} -eq 0 ]] && exit 0

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}"
PLUGIN_CACHE="$CACHE_DIR/dotfiles-plugins"
PLUGIN_STAMP="$CACHE_DIR/dotfiles-plugins-stamp"
INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
FETCH_TTL=300

log()  { printf '     %s\n' "$1"; }
warn() { printf '     %s\n' "$1" >&2; }

plugin_installed() {
    [[ -f "$INSTALLED_JSON" ]] && grep -q "\"${1}\"" "$INSTALLED_JSON"
}

# Skip fetch if FETCH_HEAD was updated less than FETCH_TTL seconds ago
fetch_is_fresh() {
    local fh="$1/.git/FETCH_HEAD"
    [[ -f "$fh" ]] || return 1
    local mtime; mtime=$(stat -c %Y "$fh" 2>/dev/null || /usr/bin/stat -f %m "$fh" 2>/dev/null) || return 1
    (( $(date +%s) - mtime < FETCH_TTL ))
}

_plugin_fingerprint() {
    local input; input="$(printf '%s\n' "${PLUGINS[@]}")"
    [[ -f "$INSTALLED_JSON" ]] && input+=$'\n'"$(cat "$INSTALLED_JSON")"
    printf '%s' "$input" | shasum -a 256 | cut -d' ' -f1
}

command -v claude &>/dev/null || exit 0

_current_fp="$(_plugin_fingerprint)"
[[ -f "$PLUGIN_STAMP" ]] && [[ "$(cat "$PLUGIN_STAMP")" == "$_current_fp" ]] && exit 0

mkdir -p "$PLUGIN_CACHE"

# Phase 1: Clone missing repos, fetch stale repos in parallel
fetch_pids=()
for slug in "${PLUGINS[@]}"; do
    dir="$PLUGIN_CACHE/${slug//\//__}"
    if [[ -d "$dir/.git" ]]; then
        if ! fetch_is_fresh "$dir"; then
            ( git -C "$dir" fetch --depth=1 origin >/dev/null 2>&1 \
                && git -C "$dir" reset --hard origin/HEAD >/dev/null 2>&1 \
                || true ) &
            fetch_pids+=($!)
        fi
    else
        gh repo clone "$slug" "$dir" -- --depth 1 2>/dev/null \
            || warn "fail clone $slug"
    fi
done
for pid in "${fetch_pids[@]+"${fetch_pids[@]}"}"; do
    wait "$pid" 2>/dev/null || true
done

# Phase 2: Register marketplaces and install plugins
py="$HOME/.venv/bin/python3"
[[ -x "$py" ]] || py="$(command -v python3 2>/dev/null || true)"

for slug in "${PLUGINS[@]}"; do
    base="${slug##*/}"
    dir="$PLUGIN_CACHE/${slug//\//__}"
    [[ -d "$dir/.git" ]] || continue
    if [[ ! -x "${py:-}" ]]; then warn "skip plugin/$base (no python3)"; continue; fi

    mp_json="$dir/.claude-plugin/marketplace.json"
    [[ -f "$mp_json" ]] || { warn "skip plugin/$base (no marketplace.json)"; continue; }

    km_file="$HOME/.claude/plugins/known_marketplaces.json"
    mkdir -p "$(dirname "$km_file")"
    [[ -f "$km_file" ]] || echo '{}' > "$km_file"
    abs_dir="$(cd "$dir" && pwd)"

    # Read marketplace + plugin names from marketplace.json, sync known_marketplaces.json,
    # emit "<plugin>@<marketplace>" slug for install.
    install_slug=$("$py" - "$mp_json" "$km_file" "$abs_dir" << 'PYEOF'
import json, sys
mp_path, km_path, install_dir = sys.argv[1], sys.argv[2], sys.argv[3]
with open(mp_path) as f: mp = json.load(f)
mp_name = mp["name"]
plugin_name = mp["plugins"][0]["name"]
with open(km_path) as f: data = json.load(f)
if data.get(mp_name, {}).get("installLocation") != install_dir:
    data[mp_name] = {"source": {"source": "directory", "path": install_dir}, "installLocation": install_dir, "lastUpdated": "2026-01-01T00:00:00.000Z"}
    with open(km_path, "w") as f: json.dump(data, f, indent=2); f.write("\n")
print(f"{plugin_name}@{mp_name}")
PYEOF
) || { warn "fail parse plugin/$base"; continue; }

    if ! plugin_installed "$install_slug"; then
        claude plugin install "$install_slug" 2>/dev/null \
            && log "add plugin/$install_slug" || warn "fail plugin/$install_slug"
    fi
done

mkdir -p "$(dirname "$PLUGIN_STAMP")"
printf '%s' "$_current_fp" > "$PLUGIN_STAMP"
