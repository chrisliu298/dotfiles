#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Declarative tables ───────────────────────────────────────────

LINKS=(
    "shell/.aliases:.aliases"
    "shell/.functions:.functions"
    "shell/.p10k.zsh:.p10k.zsh"
    "shell/.zshenv:.zshenv"
    "shell/.zshrc:.zshrc"
    ".config/btop:.config/btop"
    ".config/nvim:.config/nvim"
    ".config/tmux:.config/tmux"
    "agents/claude/CLAUDE.md:.claude/CLAUDE.md"
    "agents/claude/keybindings.json:.claude/keybindings.json"
    "agents/claude/hooks:.claude/hooks"
    "agents/claude/statusline-command.sh:.claude/statusline-command.sh"
    "agents/codex/AGENTS.md:.codex/AGENTS.md"
    "agents/extensions/skills/relay/scripts/relay:.local/bin/relay"
)

# name|source|agents
# name: skill name, or * to auto-discover subdirs with SKILL.md
# source: ./path (local dir) or owner/repo[/subpath] (GitHub)
# agents: claude,codex | claude | codex
SKILLS=(
    # Local extensions (wildcard: all subdirs with SKILL.md)
    "*|./agents/extensions/skills|claude,codex"

    # Relay: agent-specific SKILL.md (not caught by wildcard — no top-level SKILL.md)
    "relay|./agents/extensions/skills/relay/claude|claude"
    "relay|./agents/extensions/skills/relay/codex|codex"

    # Third-party
    "defuddle|kepano/obsidian-skills/skills/defuddle|claude,codex"
    "humanizer|blader/humanizer|claude,codex"
    "obsidian-cli|kepano/obsidian-skills/skills/obsidian-cli|claude,codex"
    "runpodctl|runpod/skills/runpodctl|claude,codex"

    # Agent-specific (same name, different source per agent)
    "pdf|anthropics/skills/skills/pdf|claude"
    "skill-creator|anthropics/skills/skills/skill-creator|claude"
    "pdf|openai/skills/skills/.curated/pdf|codex"
)

# slug:dest (clone → symlink to ~/dest)
REPOS=(
    "chrisliu298/ghostty-config:.config/ghostty"
)

# name|command|args (user-scoped MCP servers for Claude Code)
MCP_SERVERS=(
    "playwright|npx|@playwright/mcp@latest --headless --codegen none --console-level error"
    "codex|codex|mcp-server"
)

PLUGINS=(
    "chrisliu298/nanoresearch"
)

# Skills to sync from agents/extensions/skills/ → ~/Developer/GitHub/<name>/
PUBLISH_SKILLS=(
    "autoresearch"
    "citation-assistant"
    "deslop"
    "interviewer"
    "last-call"
    "lbreview"
    "nanorepl"
    "note-gen"
    "prism"
    "prompt-engineer"
    "recall"
    "relay"
    "vault-linker"
)

REPO_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles-repos"
PLUGIN_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles-plugins"
SKILL_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/skills-src"
MANIFEST="$HOME/.dotfiles-managed"

# ── Output helpers ───────────────────────────────────────────────

# ANSI colors (auto-disabled when stdout is not a terminal)
if [[ -t 1 ]]; then
    _DIM=$'\033[2m'    _BOLD=$'\033[1m'
    _GRN=$'\033[32m'   _YLW=$'\033[33m'   _RED=$'\033[31m'   _CYN=$'\033[36m'
    _RST=$'\033[0m'
else
    _DIM="" _BOLD="" _GRN="" _YLW="" _RED="" _CYN="" _RST=""
fi

# Per-section OK counter (batched, printed once via flush_ok)
_sec_ok=0
# Global totals for the final summary line
_total_ok=0 _total_new=0 _total_skip=0 _total_clean=0 _total_fail=0

# ── Section header ───────────────────────────────
section() {
    local title="$1"
    local total_width=60
    local prefix="  ── $title "
    local pad_width=$(( total_width - ${#prefix} ))
    local pad="" i
    (( pad_width < 4 )) && pad_width=4
    for (( i = 0; i < pad_width; i++ )); do pad+="─"; done
    printf '\n  %s── %s %s%s\n' "${_BOLD}${_CYN}" "$title" "$pad${_RST}" ""
    _sec_ok=0
}

# Flush batched OK count as one compact line, then reset
flush_ok() {
    if (( _sec_ok > 0 )); then
        printf '     %s✓ %d unchanged%s\n' "$_DIM" "$_sec_ok" "$_RST"
        (( _total_ok += _sec_ok ))
        _sec_ok=0
    fi
}

# ── Status printers ──────────────────────────────
# ok() is silent — it just increments the batch counter.
# Everything else prints immediately so changes/errors are visible.
ok()      { (( ++_sec_ok )); }
new()     { (( ++_total_new ));   printf '     🔗 %s%s%s\n' "$_GRN" "$1" "$_RST"; }
skip()    { (( ++_total_skip ));  printf '     %s⏭️  %s%s\n' "$_YLW" "$1" "$_RST"; }
cleaned() { (( ++_total_clean )); printf '     %s🧹 %s%s\n' "$_DIM" "$1" "$_RST"; }
fail()    { (( ++_total_fail ));  printf '     %s❌ %s%s\n' "$_RED" "$1" "$_RST" >&2; }
added()   { (( ++_total_new ));   printf '     ➕ %s%s%s\n' "$_GRN" "$1" "$_RST"; }
wrote()   { (( ++_total_new ));   printf '     🔀 %s%s%s\n' "$_CYN" "$1" "$_RST"; }

# Final summary bar: "42 ok | 2 changed | 1 skipped"
print_summary() {
    local parts=()
    (( _total_ok > 0 ))    && parts+=("${_GRN}${_total_ok} ok${_RST}")
    (( _total_new > 0 ))   && parts+=("${_CYN}${_total_new} changed${_RST}")
    (( _total_skip > 0 ))  && parts+=("${_YLW}${_total_skip} skipped${_RST}")
    (( _total_clean > 0 )) && parts+=("${_YLW}${_total_clean} cleaned${_RST}")
    (( _total_fail > 0 ))  && parts+=("${_RED}${_total_fail} failed${_RST}")
    local result="" i
    for (( i = 0; i < ${#parts[@]}; i++ )); do
        (( i > 0 )) && result+="  ${_DIM}|${_RST}  "
        result+="${parts[$i]}"
    done
    printf '\n  %s\n' "$result"
}

# ── Functions ────────────────────────────────────────────────────

ensure_link() {
    local src="$ROOT/$1" dest="$HOME/$2"
    local label="~/$2"
    if [[ ! -e "$src" ]]; then
        skip "$label (source not found)"
        return
    fi
    if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
        ok "$label"
        return
    fi
    mkdir -p "$(dirname "$dest")"
    rm -rf "$dest"
    ln -s "$src" "$dest"
    new "$label"
}

clean_stale_managed() {
    [[ -f "$MANIFEST" ]] || return 0

    local current_links="" current_repos="" current_mcp=""
    local entry
    for entry in "${LINKS[@]}"; do current_links+="${entry#*:}"$'\n'; done
    for entry in ${REPOS[@]+"${REPOS[@]}"}; do current_repos+="${entry#*:}"$'\n'; done
    for entry in ${MCP_SERVERS[@]+"${MCP_SERVERS[@]}"}; do
        IFS='|' read -r name _ _ <<< "$entry"
        current_mcp+="$name"$'\n'
    done

    while IFS=: read -r type value; do
        [[ -z "$type" || -z "$value" ]] && continue
        case "$type" in
            link|repo)
                echo "$current_links$current_repos" | grep -qxF "$value" && continue
                if [[ -L "$HOME/$value" ]]; then
                    rm -f "$HOME/$value"
                    cleaned "~/$value (stale $type)"
                fi
                ;;
            mcp)
                echo "$current_mcp" | grep -qxF "$value" && continue
                local removed=false
                if command -v claude &>/dev/null && claude mcp remove -s user "$value" 2>/dev/null; then
                    removed=true
                fi
                if command -v codex &>/dev/null && codex mcp remove "$value" 2>/dev/null; then
                    removed=true
                fi
                $removed && cleaned "mcp/$value (stale server)"
                ;;
        esac
    done < "$MANIFEST"
}

write_manifest() {
    local tmp="${MANIFEST}.tmp.$$"
    local entry
    : > "$tmp"
    for entry in "${LINKS[@]}"; do echo "link:${entry#*:}"; done >> "$tmp"
    for entry in ${REPOS[@]+"${REPOS[@]}"}; do echo "repo:${entry#*:}"; done >> "$tmp"
    for entry in ${MCP_SERVERS[@]+"${MCP_SERVERS[@]}"}; do
        IFS='|' read -r name _ _ <<< "$entry"
        echo "mcp:$name"
    done >> "$tmp"
    mv "$tmp" "$MANIFEST"
}

install_repos() {
    mkdir -p "$REPO_CACHE"
    local entry
    for entry in "${REPOS[@]}"; do
        local slug="${entry%%:*}" dest_rel="${entry#*:}"
        local dir="$REPO_CACHE/${slug//\//__}"
        local dest="$HOME/$dest_rel"
        local label="~/$dest_rel"
        if [[ -d "$dir/.git" ]]; then
            git -C "$dir" pull --ff-only -q 2>/dev/null || true
        else
            git clone "https://github.com/$slug.git" "$dir" 2>/dev/null || {
                fail "clone $slug"; continue
            }
        fi
        if [[ -L "$dest" && "$(readlink "$dest")" == "$dir" ]]; then
            ok "$label"
        else
            mkdir -p "$(dirname "$dest")"
            rm -rf "$dest"
            ln -s "$dir" "$dest"
            new "$label"
        fi
    done
}

sync_repo() {
    local slug="$1"
    local dir="$SKILL_CACHE/${slug//\//__}"
    if [[ -d "$dir/.git" ]]; then
        git -C "$dir" fetch --depth=1 origin 2>/dev/null \
            && git -C "$dir" reset --hard origin/HEAD 2>/dev/null \
            || true
    else
        [[ -e "$dir" ]] && rm -rf "$dir"
        mkdir -p "$SKILL_CACHE"
        git clone --depth 1 "https://github.com/$slug.git" "$dir" 2>/dev/null || {
            fail "clone $slug"; return 1
        }
    fi
    echo "$dir"
}

ensure_skill_link() {
    local src="$1" dest="$2"
    if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
        ok "~${dest#$HOME}"
    else
        rm -rf "$dest"
        ln -s "$src" "$dest"
        new "~${dest#$HOME}"
    fi
}

install_skills() {
    # Phase 0: Collect unique GitHub repo slugs and clone in parallel
    local repos=()
    local entry
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name source agents <<< "$entry"
        [[ "$source" == ./* ]] && continue
        local _rest="${source#*/}" _owner="${source%%/*}"
        local slug="$_owner/${_rest%%/*}"
        local already=false r
        for r in ${repos[@]+"${repos[@]}"}; do [[ "$r" == "$slug" ]] && already=true && break; done
        $already || repos+=("$slug")
    done
    if (( ${#repos[@]} )); then
        mkdir -p "$SKILL_CACHE"
        for r in "${repos[@]}"; do sync_repo "$r" >/dev/null & done
        wait
    fi

    # Phase 1: Resolve entries and create symlinks
    mkdir -p "$HOME/.claude/skills" "$HOME/.codex/skills"
    local claude_expected="" codex_expected=""
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name source agents <<< "$entry"

        # Resolve source to a local path
        local base_dir repo_name=""
        if [[ "$source" == ./* ]]; then
            base_dir="$ROOT/${source#./}"
        else
            local _rest="${source#*/}" _owner="${source%%/*}"
            repo_name="${_rest%%/*}"
            local slug="$_owner/$repo_name"
            base_dir="$SKILL_CACHE/${slug//\//__}"
            local subpath="${_rest#*/}"
            [[ "$subpath" != "$_rest" ]] && base_dir="$base_dir/$subpath"
        fi
        if [[ ! -d "$base_dir" ]]; then
            skip "$name (source not found: $source)"
            continue
        fi

        # Expand wildcard or resolve single skill
        local -a skill_entries=()
        if [[ "$name" == "*" ]]; then
            if [[ -f "$base_dir/SKILL.md" ]]; then
                skill_entries+=("${repo_name:-$(basename "$base_dir")}:$base_dir")
            else
                local d
                for d in "$base_dir"/*/; do
                    [[ -f "$d/SKILL.md" ]] || continue
                    d="${d%/}"
                    skill_entries+=("$(basename "$d"):$d")
                done
            fi
        else
            if [[ -f "$base_dir/SKILL.md" ]]; then
                skill_entries+=("$name:$base_dir")
            else
                skip "$name (no SKILL.md at $source)"
            fi
        fi

        # Create symlinks for each resolved skill
        local se
        for se in ${skill_entries[@]+"${skill_entries[@]}"}; do
            local sname="${se%%:*}" spath="${se#*:}"
            if [[ "$agents" == *claude* ]]; then
                ensure_skill_link "$spath" "$HOME/.claude/skills/$sname"
                claude_expected+="$sname"$'\n'
            fi
            if [[ "$agents" == *codex* ]]; then
                ensure_skill_link "$spath" "$HOME/.codex/skills/$sname"
                codex_expected+="$sname"$'\n'
            fi
        done
    done

    # Phase 2: Clean stale entries
    local dir expected
    for dir in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
        [[ -d "$dir" ]] || continue
        [[ "$dir" == *claude* ]] && expected="$claude_expected" || expected="$codex_expected"
        for entry in "$dir"/*; do
            [[ -e "$entry" || -L "$entry" ]] || continue
            local bname="${entry##*/}"
            [[ "$bname" == .* ]] && continue
            [[ $'\n'"$expected" == *$'\n'"$bname"$'\n'* ]] && continue
            if [[ -L "$entry" ]]; then
                rm -f "$entry"
                cleaned "${entry/#$HOME/~}"
            else
                rm -rf "$entry"
                cleaned "${entry/#$HOME/~} (unmanaged)"
            fi
        done
    done

    # One-time migration: clean old intermediate directories
    if [[ -d "$HOME/.agents" ]]; then
        rm -rf "$HOME/.agents/skills" "$HOME/.agents/skills-override" "$HOME/.agents/.dotfiles-managed"
        rm -f "$HOME/.agents/.skill-lock.json"
        rmdir "$HOME/.agents" 2>/dev/null || true
    fi

    # Prune stale cache repos no longer in SKILLS table
    if [[ -d "$SKILL_CACHE" ]]; then
        local cached
        for cached in "$SKILL_CACHE"/*/; do
            [[ -d "$cached" ]] || continue
            local cname="${cached%/}"; cname="${cname##*/}"
            local found=false
            for r in ${repos[@]+"${repos[@]}"}; do [[ "${r//\//__}" == "$cname" ]] && found=true && break; done
            $found || { rm -rf "$cached"; cleaned "cache/$cname"; }
        done
    fi
}

install_mcp_servers() {
    local entry name cmd args

    # Claude Code
    if command -v claude &>/dev/null; then
        for entry in "${MCP_SERVERS[@]}"; do
            IFS='|' read -r name cmd args <<< "$entry"
            if claude mcp list 2>/dev/null | grep -q "^$name:"; then
                ok "claude/$name"
            else
                if claude mcp add --scope user "$name" -- $cmd $args 2>/dev/null; then
                    added "claude/$name"
                else
                    fail "claude/$name"
                fi
            fi
        done
    else
        skip "claude CLI not found"
    fi

    # Codex
    if command -v codex &>/dev/null; then
        for entry in "${MCP_SERVERS[@]}"; do
            IFS='|' read -r name cmd args <<< "$entry"
            [[ "$name" == "codex" ]] && continue
            if codex mcp get "$name" &>/dev/null; then
                ok "codex/$name"
            else
                if codex mcp add "$name" -- $cmd $args 2>/dev/null; then
                    added "codex/$name"
                else
                    fail "codex/$name"
                fi
            fi
        done
    else
        skip "codex CLI not found"
    fi
}

write_codex_config() {
    mkdir -p "$HOME/.codex"
    if ! "$HOME/.venv/bin/python3" << 'PYEOF'
import os, tomllib

def merge(a, b):
    r = dict(a)
    for k, v in b.items():
        r[k] = merge(r[k], v) if k in r and isinstance(r[k], dict) and isinstance(v, dict) else v
    return r

def fmt(v):
    if isinstance(v, bool): return str(v).lower()
    if isinstance(v, int): return str(v)
    if isinstance(v, str): return f'"{v}"'
    if isinstance(v, list): return "[" + ", ".join(fmt(i) for i in v) + "]"

def qk(k):
    import re
    return k if re.match(r'^[A-Za-z0-9_-]+$', k) else f'"{k}"'

def write(data, f, prefix=""):
    for k, v in data.items():
        if not isinstance(v, dict): f.write(f"{qk(k)} = {fmt(v)}\n")
    for k, v in data.items():
        if not isinstance(v, dict): continue
        sec = f"{prefix}.{qk(k)}" if prefix else qk(k)
        direct = [(kk, vv) for kk, vv in v.items() if not isinstance(vv, dict)]
        nested = [(kk, vv) for kk, vv in v.items() if isinstance(vv, dict)]
        if direct or not nested:
            f.write(f"\n[{sec}]\n")
            for kk, vv in direct: f.write(f"{qk(kk)} = {fmt(vv)}\n")
        for kk, vv in nested: write({kk: vv}, f, sec)

path = os.path.expanduser("~/.codex/config.toml")
desired = {
    "model": "gpt-5.4",
    "model_reasoning_effort": "high",
    "personality": "pragmatic",
    "responses_websockets_v2": True,
    "suppress_unstable_features_warning": True,
    "model_context_window": 1000000,
    "model_auto_compact_token_limit": 900000,
    "agents": {"max_depth": 2, "max_threads": 12},
    "features": {"multi_agent": True, "prevent_idle_sleep": True, "voice_transcription": True},
    "tui": {"status_line": ["model-with-reasoning", "current-dir", "git-branch", "context-used", "weekly-limit", "context-window-size"]},
    "mcp_servers": {"playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest", "--headless", "--codegen", "none", "--console-level", "error"]}},
}
existing = {}
if os.path.isfile(path):
    with open(path, "rb") as f: existing = tomllib.load(f)
with open(path, "w") as f: write(merge(existing, desired), f)
PYEOF
    then
        fail "~/.codex/config.toml (python3 with tomllib required)"
        return
    fi
    wrote "~/.codex/config.toml"
}

install_plugins() {
    if ! command -v claude &>/dev/null; then
        skip "claude CLI not found"
        return
    fi

    mkdir -p "$PLUGIN_CACHE"
    local slug
    for slug in "${PLUGINS[@]}"; do
        local name="${slug##*/}"
        local dir="$PLUGIN_CACHE/${slug//\//__}"

        # Clone or update (use gh for private repo auth)
        if [[ -d "$dir/.git" ]]; then
            git -C "$dir" fetch --depth=1 origin >/dev/null 2>&1 \
                && git -C "$dir" reset --hard origin/HEAD >/dev/null 2>&1 \
                || true
        else
            gh repo clone "$slug" "$dir" -- --depth 1 2>/dev/null || {
                fail "clone $slug"; continue
            }
        fi

        # Register marketplace in known_marketplaces.json so claude can discover the plugin
        local km_file="$HOME/.claude/plugins/known_marketplaces.json"
        mkdir -p "$(dirname "$km_file")"
        [[ -f "$km_file" ]] || echo '{}' > "$km_file"
        local abs_dir
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
            ok "plugin/$name"
        else
            if claude plugin install "$name@$name" 2>/dev/null; then
                added "plugin/$name"
            else
                fail "plugin/$name"
            fi
        fi
    done
}

install_claude_settings() {
    local src="$ROOT/agents/claude/settings.json"
    local dest="$HOME/.claude/settings.json"
    local label="~/.claude/settings.json"
    [[ -f "$src" ]] || { skip "$label (source not found)"; return; }
    mkdir -p "$(dirname "$dest")"
    # Expand ~ to $HOME so Claude Code resolves absolute paths correctly
    local content
    content=$(sed "s|~/|$HOME/|g" "$src")
    if [[ -f "$dest" && ! -L "$dest" ]] && [[ "$(cat "$dest")" == "$content" ]]; then
        ok "$label"
    else
        rm -f "$dest"
        printf '%s\n' "$content" > "$dest"
        wrote "$label"
    fi
}

sync_published_skills() {
    local dev_dir="$HOME/Developer/GitHub"
    local skills_dir="$ROOT/agents/extensions/skills"
    local name

    for name in "${PUBLISH_SKILLS[@]}"; do
        local repo_dir="$dev_dir/$name"
        local skill_dir="$skills_dir/$name"

        if ! git -C "$repo_dir" rev-parse --is-inside-work-tree &>/dev/null; then
            skip "publish/$name (no repo)"
            continue
        fi
        if [[ ! -d "$skill_dir" ]]; then
            skip "publish/$name (no local skill)"
            continue
        fi

        # Skip dirty repos to avoid overwriting uncommitted work
        if ! git -C "$repo_dir" diff --quiet 2>/dev/null \
            || ! git -C "$repo_dir" diff --cached --quiet 2>/dev/null \
            || [[ -n "$(git -C "$repo_dir" ls-files --others --exclude-standard 2>/dev/null)" ]]; then
            skip "publish/$name (repo dirty)"
            continue
        fi

        if [[ "$name" == "relay" ]]; then
            mkdir -p "$repo_dir/claude/skills/relay" "$repo_dir/codex/skills/relay" "$repo_dir/scripts"
            rsync -a --delete --exclude='scripts/' \
                "$skill_dir/claude/" "$repo_dir/claude/skills/relay/"
            rsync -a --delete --exclude='scripts/' \
                "$skill_dir/codex/" "$repo_dir/codex/skills/relay/"
            rsync -a --delete "$skill_dir/scripts/" "$repo_dir/scripts/"
        else
            rsync -a --delete \
                --exclude='.git' --exclude='LICENSE' --exclude='README.md' \
                --exclude='.gitignore' --exclude='.relay' \
                "$skill_dir/" "$repo_dir/"
        fi

        if git -C "$repo_dir" diff --quiet 2>/dev/null \
            && [[ -z "$(git -C "$repo_dir" ls-files --others --exclude-standard 2>/dev/null)" ]]; then
            ok "publish/$name"
        else
            wrote "publish/$name"
        fi
    done
}

# ── Main ─────────────────────────────────────────────────────────

main() {
    cd "$ROOT"

    printf '\n  %s%s dotfiles%s  %s%s%s\n' \
        "${_BOLD}${_CYN}" "🔧" "$_RST" "$_DIM" "$ROOT" "$_RST"

    # Cleanup stale managed items
    section "Cleanup"
    clean_stale_managed
    flush_ok

    # Submodules
    section "Submodules"
    if [[ -f .gitmodules && -s .gitmodules ]]; then
        git submodule sync --recursive >/dev/null 2>&1
        git submodule update --init --recursive >/dev/null 2>&1
        ok "synced"
    else
        skip "no submodules found"
    fi
    flush_ok

    # Symlinks
    section "Symlinks"
    local entry
    for entry in "${LINKS[@]}"; do
        ensure_link "${entry%%:*}" "${entry#*:}"
    done
    install_claude_settings
    flush_ok

    # External repos
    section "Repos"
    install_repos
    flush_ok

    # Extensions
    section "Extensions"
    install_skills
    flush_ok

    # Codex config
    section "Codex Config"
    write_codex_config
    flush_ok

    # MCP servers
    section "MCP Servers"
    install_mcp_servers
    flush_ok

    # Publish skills to repos (opt-in: ./dotfiles.sh publish)
    if [[ "${1:-}" == "publish" ]]; then
        section "Publish"
        sync_published_skills
        flush_ok
    fi

    # Plugins
    section "Plugins"
    install_plugins
    flush_ok

    # Record managed state for future cleanup
    write_manifest

    # Final summary
    print_summary
    printf '  ✨ %sDone.%s Restart your shell or %ssource ~/.zshrc%s\n\n' \
        "$_BOLD" "$_RST" "$_DIM" "$_RST"
}

main "$@"
