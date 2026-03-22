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
)

# name|source|agents
# name: skill name, or * to auto-discover subdirs with SKILL.md
# source: ./path (local dir) or owner/repo[/subpath] (GitHub)
# agents: claude,codex | claude | codex
SKILLS=(
    # Local extensions (wildcard: all subdirs with SKILL.md)
    "*|./agents/extensions/skills|claude,codex"

    # Claude-only local skills (explicit entries override the wildcard's agents setting)
    "chatgpt|./agents/extensions/skills/chatgpt|claude"

    # Relay: agent-specific SKILL.md (not caught by wildcard — no top-level SKILL.md)
    "relay|./agents/extensions/skills/relay/claude|claude"
    "relay|./agents/extensions/skills/relay/codex|codex"

    # Third-party
    "defuddle|kepano/obsidian-skills/skills/defuddle|claude,codex"
    "humanizer|blader/humanizer|claude,codex"
    "obsidian-bases|kepano/obsidian-skills/skills/obsidian-bases|claude,codex"
    "obsidian-cli|kepano/obsidian-skills/skills/obsidian-cli|claude,codex"
    "browser-use|browser-use/browser-use/skills/browser-use|claude,codex"
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

REPO_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles-repos"
SKILL_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/skills-src"

# ── Helpers ──────────────────────────────────────────────────────

if [[ -t 1 ]]; then
    _CYN=$'\033[1;36m' _YLW=$'\033[33m' _DIM=$'\033[2m' _RST=$'\033[0m'
else
    _CYN="" _YLW="" _DIM="" _RST=""
fi

section() { printf '  %s── %s ──%s\n' "$_CYN" "$1" "$_RST"; }
log()     { printf '     %s\n' "$1"; }
warn()    { printf '     %s%s%s\n' "$_YLW" "$1" "$_RST" >&2; }

ensure_symlink() {
    local src="$1" dest="$2"
    [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]] && return
    mkdir -p "$(dirname "$dest")"
    rm -rf "$dest"
    ln -s "$src" "$dest"
    log "link ${dest/#$HOME/~}"
}

sync_git_checkout() {
    local slug="$1" dir="$2"
    if [[ -d "$dir/.git" ]]; then
        git -C "$dir" fetch --depth=1 origin >/dev/null 2>&1 \
            && git -C "$dir" reset --hard origin/HEAD >/dev/null 2>&1 \
            || true
    else
        # Remove corrupt/partial cache before cloning
        [[ -e "$dir" ]] && rm -rf "$dir"
        mkdir -p "$(dirname "$dir")"
        git clone --depth 1 "https://github.com/$slug.git" "$dir" 2>/dev/null || {
            warn "fail clone $slug"; return 1
        }
    fi
}

# ── Install functions ────────────────────────────────────────────

install_links() {
    local entry
    for entry in "${LINKS[@]}"; do
        local src="$ROOT/${entry%%:*}"
        [[ -e "$src" ]] || { warn "skip ~/${entry#*:} (source missing)"; continue; }
        ensure_symlink "$src" "$HOME/${entry#*:}"
    done

    # settings.json: copy with ~ expansion (Claude Code needs absolute paths)
    local src="$ROOT/agents/claude/settings.json"
    local dest="$HOME/.claude/settings.json"
    if [[ -f "$src" ]]; then
        local content
        content=$(sed "s|~/|$HOME/|g" "$src")
        if [[ -f "$dest" && ! -L "$dest" ]] && [[ "$(cat "$dest")" == "$content" ]]; then
            : # unchanged
        else
            mkdir -p "$(dirname "$dest")"
            rm -f "$dest"
            printf '%s\n' "$content" > "$dest"
            log "write ~/.claude/settings.json"
        fi
    fi
}

install_repos() {
    mkdir -p "$REPO_CACHE"
    local entry
    for entry in "${REPOS[@]}"; do
        local slug="${entry%%:*}" dest_rel="${entry#*:}"
        local dir="$REPO_CACHE/${slug//\//__}"
        if [[ -d "$dir/.git" ]]; then
            # Safe update: skip if dirty, fast-forward only
            if ! git -C "$dir" diff --quiet 2>/dev/null; then
                warn "skip $slug (dirty)"
            else
                git -C "$dir" pull --ff-only -q 2>/dev/null || true
            fi
        else
            mkdir -p "$(dirname "$dir")"
            git clone "https://github.com/$slug.git" "$dir" 2>/dev/null || {
                warn "fail clone $slug"; continue
            }
        fi
        ensure_symlink "$dir" "$HOME/$dest_rel"
    done
}

install_skills() {
    # Clone unique GitHub repos in parallel
    local repos=()
    local entry
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r _ source _ <<< "$entry"
        [[ "$source" == ./* ]] && continue
        local _rest="${source#*/}" _owner="${source%%/*}"
        local slug="$_owner/${_rest%%/*}"
        local already=false r
        for r in ${repos[@]+"${repos[@]}"}; do
            if [[ "$r" == "$slug" ]]; then already=true; break; fi
        done
        $already || repos+=("$slug")
    done
    if (( ${#repos[@]} )); then
        mkdir -p "$SKILL_CACHE"
        for r in "${repos[@]}"; do sync_git_checkout "$r" "$SKILL_CACHE/${r//\//__}" & done
        wait
    fi

    # Resolve entries and create symlinks
    mkdir -p "$HOME/.claude/skills" "$HOME/.codex/skills"
    # Collect explicitly named skills so the wildcard skips them
    local explicit_names=""
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name _ _ <<< "$entry"
        [[ "$name" != "*" ]] && explicit_names+="$name"$'\n'
    done

    local claude_expected="" codex_expected=""
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name source agents <<< "$entry"

        local base_dir
        if [[ "$source" == ./* ]]; then
            base_dir="$ROOT/${source#./}"
        else
            local _rest="${source#*/}" _owner="${source%%/*}"
            local slug="$_owner/${_rest%%/*}"
            base_dir="$SKILL_CACHE/${slug//\//__}"
            local subpath="${_rest#*/}"
            [[ "$subpath" != "$_rest" ]] && base_dir="$base_dir/$subpath"
        fi
        [[ -d "$base_dir" ]] || { warn "skip $name (source not found: $source)"; continue; }

        local -a skill_entries=()
        if [[ "$name" == "*" ]]; then
            if [[ -f "$base_dir/SKILL.md" ]]; then
                skill_entries+=("$(basename "$base_dir"):$base_dir")
            else
                local d
                for d in "$base_dir"/*/; do
                    [[ -f "$d/SKILL.md" ]] || continue
                    d="${d%/}"
                    local dname="$(basename "$d")"
                    # Skip skills that have explicit entries (they override the wildcard's agents)
                    echo "$explicit_names" | grep -qx "$dname" && continue
                    skill_entries+=("$dname:$d")
                done
            fi
        else
            [[ -f "$base_dir/SKILL.md" ]] \
                && skill_entries+=("$name:$base_dir") \
                || warn "skip $name (no SKILL.md at $source)"
        fi

        local se
        for se in ${skill_entries[@]+"${skill_entries[@]}"}; do
            local sname="${se%%:*}" spath="${se#*:}"
            if [[ "$agents" == *claude* ]]; then
                ensure_symlink "$spath" "$HOME/.claude/skills/$sname"
                claude_expected+="$sname"$'\n'
            fi
            if [[ "$agents" == *codex* ]]; then
                ensure_symlink "$spath" "$HOME/.codex/skills/$sname"
                codex_expected+="$sname"$'\n'
            fi
        done
    done

    # Clean stale skill symlinks
    local dir expected
    for dir in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
        [[ -d "$dir" ]] || continue
        [[ "$dir" == *claude* ]] && expected="$claude_expected" || expected="$codex_expected"
        for entry in "$dir"/*; do
            [[ -e "$entry" || -L "$entry" ]] || continue
            local bname="${entry##*/}"
            [[ "$bname" == .* ]] && continue
            [[ $'\n'"$expected" == *$'\n'"$bname"$'\n'* ]] && continue
            rm -rf "$entry"
            log "clean ${entry/#$HOME/~}"
        done
    done

    # Prune stale cache repos
    if [[ -d "$SKILL_CACHE" ]]; then
        local cached
        for cached in "$SKILL_CACHE"/*/; do
            [[ -d "$cached" ]] || continue
            local cname="${cached%/}"; cname="${cname##*/}"
            local found=false
            for r in ${repos[@]+"${repos[@]}"}; do
                if [[ "${r//\//__}" == "$cname" ]]; then found=true; break; fi
            done
            $found || { rm -rf "$cached"; log "clean cache/$cname"; }
        done
    fi
}

install_codex_config() {
    local src="$ROOT/agents/codex/config.toml"
    local dest="$HOME/.codex/config.toml"
    [[ -f "$src" ]] || return
    mkdir -p "$HOME/.codex"
    # Merge managed keys into existing config (preserves user additions)
    if ! "$HOME/.venv/bin/python3" - "$src" "$dest" << 'PYEOF' 2>/dev/null
import sys, tomllib
src, dest = sys.argv[1], sys.argv[2]
with open(src, "rb") as f: desired = tomllib.load(f)
existing = {}
try:
    with open(dest, "rb") as f: existing = tomllib.load(f)
except FileNotFoundError: pass
def merge(a, b):
    r = dict(a)
    for k, v in b.items():
        r[k] = merge(r[k], v) if k in r and isinstance(r[k], dict) and isinstance(v, dict) else v
    return r
merged = merge(existing, desired)
if merged == existing: sys.exit(0)
# Write TOML (simple key=value and [section] format)
def fmt(v):
    if isinstance(v, bool): return str(v).lower()
    if isinstance(v, int): return str(v)
    if isinstance(v, str): return f'"{v}"'
    if isinstance(v, list): return "[" + ", ".join(fmt(i) for i in v) + "]"
def write(data, f, prefix=""):
    for k, v in data.items():
        if not isinstance(v, dict): f.write(f"{k} = {fmt(v)}\n")
    for k, v in data.items():
        if not isinstance(v, dict): continue
        sec = f"{prefix}.{k}" if prefix else k
        direct = [(kk, vv) for kk, vv in v.items() if not isinstance(vv, dict)]
        nested = [(kk, vv) for kk, vv in v.items() if isinstance(vv, dict)]
        if direct or not nested:
            f.write(f"\n[{sec}]\n")
            for kk, vv in direct: f.write(f"{kk} = {fmt(vv)}\n")
        for kk, vv in nested: write({kk: vv}, f, sec)
with open(dest, "w") as f: write(merged, f)
sys.exit(2)
PYEOF
    then
        local rc=$?
        if [[ $rc -eq 2 ]]; then
            log "write ~/.codex/config.toml"
        elif [[ $rc -ne 0 ]]; then
            # Fallback: plain copy if Python unavailable
            cp "$src" "$dest"
            log "write ~/.codex/config.toml (fallback copy)"
        fi
    fi
}

install_mcp_servers() {
    local has_claude=false has_codex=false
    if command -v claude &>/dev/null; then has_claude=true; fi
    if command -v codex &>/dev/null; then has_codex=true; fi
    $has_claude || $has_codex || { warn "neither claude nor codex CLI found"; return; }

    local entry name cmd args
    for entry in "${MCP_SERVERS[@]}"; do
        IFS='|' read -r name cmd args <<< "$entry"
        if $has_claude; then
            if ! claude mcp list 2>/dev/null | grep -q "^$name:"; then
                claude mcp add --scope user "$name" -- $cmd $args 2>/dev/null \
                    && log "add claude/$name" || warn "fail claude/$name"
            fi
        fi
        if $has_codex && [[ "$name" != "codex" ]]; then
            if ! codex mcp get "$name" &>/dev/null; then
                codex mcp add "$name" -- $cmd $args 2>/dev/null \
                    && log "add codex/$name" || warn "fail codex/$name"
            fi
        fi
    done
}

# ── Main ─────────────────────────────────────────────────────────

main() {
    cd "$ROOT"

    # Dispatch subcommands to extracted scripts
    case "${1:-}" in
        publish) exec "$ROOT/scripts/publish-skills.sh" ;;
        plugins) exec "$ROOT/scripts/install-plugins.sh" ;;
    esac

    printf '\n  %s🔧 dotfiles%s  %s%s%s\n\n' "$_CYN" "$_RST" "$_DIM" "$ROOT" "$_RST"

    section "Submodules"
    if [[ -f .gitmodules && -s .gitmodules ]]; then
        git submodule sync --recursive -q 2>/dev/null || true
        git submodule update --init --recursive -q 2>/dev/null || true
    fi
    section "Links"
    install_links
    section "Repos"
    install_repos
    section "Skills"
    install_skills
    section "Config"
    install_codex_config
    section "MCP"
    install_mcp_servers
    section "Plugins"
    "$ROOT/scripts/install-plugins.sh"

    printf '\n  ✨ Done. Restart your shell or %ssource ~/.zshrc%s\n\n' "$_DIM" "$_RST"
}

main "$@"
