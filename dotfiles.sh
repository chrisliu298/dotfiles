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
    ".config/ghostty:.config/ghostty"
    "agents/claude/CLAUDE.md:.claude/CLAUDE.md"
    "agents/claude/keybindings.json:.claude/keybindings.json"
    "agents/claude/hooks:.claude/hooks"
    "agents/claude/statusline-command.sh:.claude/statusline-command.sh"
    "agents/codex/AGENTS.md:.codex/AGENTS.md"
)

# name|source|agents — name * = auto-discover subdirs with SKILL.md
# source: ./path (local) or owner/repo[/subpath] (GitHub)
SKILLS=(
    "*|./agents/extensions/skills|claude,codex"
    # ChatGPT: agent-specific SKILL.md (no top-level SKILL.md, so wildcard skips it)
    "chatgpt|./agents/extensions/skills/chatgpt/claude|claude"
    "chatgpt|./agents/extensions/skills/chatgpt/codex|codex"
    # Relay: agent-specific SKILL.md (no top-level SKILL.md, so wildcard skips it)
    "relay|./agents/extensions/skills/relay/claude|claude"
    "relay|./agents/extensions/skills/relay/codex|codex"
    "defuddle|kepano/obsidian-skills/skills/defuddle|claude,codex"
    "humanizer|blader/humanizer|claude,codex"
    "runpodctl|runpod/skills/runpodctl|claude,codex"
    "pdf|anthropics/skills/skills/pdf|claude"
    "skill-creator|anthropics/skills/skills/skill-creator|claude"
    "pdf|openai/skills/skills/.curated/pdf|codex"
)

# Skills not auto-installed. Toggle with: ./dotfiles.sh enable/disable <name>
MANUAL_SKILLS=(
    beautify
    chatgpt
    citation-assistant
    deslop
    dump
    humanizer
    interviewer
    nanorepl
    runpodctl
    rlm
)

MCP_SERVERS=(  # name|command|args (user-scoped MCP servers)
    "chrome-devtools|npx|chrome-devtools-mcp@latest --autoConnect --channel stable --no-usage-statistics"
    "codex|codex|mcp-server"
)

SKILL_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/skills-src"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}"
GLOBAL_STAMP="$CACHE_DIR/dotfiles-global-stamp"

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

# Check stamp file against fingerprint; return 0 (fresh) or 1 (stale/missing)
stamp_fresh() {
    local stamp="$1" fp="$2"
    [[ -f "$stamp" && "$(cat "$stamp")" == "$fp" ]]
}

# Write fingerprint to stamp file
stamp_write() {
    mkdir -p "$(dirname "$1")"
    printf '%s' "$2" > "$1"
}

compute_fingerprint() {
    # Hash HEAD + working-tree changes — captures any source modification
    { git -C "$ROOT" rev-parse HEAD 2>/dev/null
      git -C "$ROOT" status --porcelain=v1 2>/dev/null; } \
        | md5 2>/dev/null || md5sum 2>/dev/null | cut -d' ' -f1
}

# Skip fetch if FETCH_HEAD was updated less than 300s ago
_fetch_fresh() {
    local fh="$1/.git/FETCH_HEAD"
    [[ -f "$fh" ]] || return 1
    local mtime; mtime=$(/usr/bin/stat -f %m "$fh" 2>/dev/null || stat -c %Y "$fh" 2>/dev/null) || return 1
    (( $(date +%s) - mtime < 300 ))
}

sync_git_checkout() {
    local slug="$1" dir="$2"
    if [[ -d "$dir/.git" ]]; then
        _fetch_fresh "$dir" && return 0
        git -C "$dir" fetch --depth=1 origin >/dev/null 2>&1 \
            && git -C "$dir" reset --hard origin/HEAD >/dev/null 2>&1 \
            || true
    else
        [[ -e "$dir" ]] && rm -rf "$dir"
        mkdir -p "$(dirname "$dir")"
        git clone --depth 1 "https://github.com/$slug.git" "$dir" 2>/dev/null || {
            warn "fail clone $slug"; return 1
        }
    fi
}

_is_manual() {
    local name="$1" m
    for m in "${MANUAL_SKILLS[@]}"; do [[ "$m" == "$name" ]] && return 0; done
    return 1
}

_resolve_source() {
    local source="$1"
    if [[ "$source" == ./* ]]; then
        printf '%s' "$ROOT/${source#./}"
    else
        local _rest="${source#*/}"
        local slug="${source%%/*}/${_rest%%/*}"
        local dir="$SKILL_CACHE/${slug//\//__}"
        local subpath="${_rest#*/}"
        [[ "$subpath" != "$_rest" ]] && dir="$dir/$subpath"
        printf '%s' "$dir"
    fi
}

_ensure_source() {
    local source="$1"
    [[ "$source" == ./* ]] && return
    local _rest="${source#*/}"
    local slug="${source%%/*}/${_rest%%/*}"
    [[ -d "$SKILL_CACHE/${slug//\//__}/.git" ]] && return
    mkdir -p "$SKILL_CACHE"
    sync_git_checkout "$slug" "$SKILL_CACHE/${slug//\//__}"
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
    local src="$ROOT/agents/claude/settings.json" dest="$HOME/.claude/settings.json"
    [[ -f "$src" ]] || return
    local content; content=$(sed "s|~/|$HOME/|g" "$src")
    if [[ -f "$dest" && ! -L "$dest" ]] && [[ "$(cat "$dest")" == "$content" ]]; then return; fi
    mkdir -p "$(dirname "$dest")"
    rm -f "$dest"
    printf '%s\n' "$content" > "$dest"
    log "write ~/.claude/settings.json"
}

_skills_repos() {
    local repos=() entry
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r _ source _ <<< "$entry"
        [[ "$source" == ./* ]] && continue
        local _rest="${source#*/}"
        local slug="${source%%/*}/${_rest%%/*}"
        local already=false r
        for r in ${repos[@]+"${repos[@]}"}; do
            [[ "$r" == "$slug" ]] && { already=true; break; }
        done
        $already || repos+=("$slug")
    done
    echo "${repos[@]+"${repos[@]}"}"
}

_fetch_skills_repos() {
    local repos; read -ra repos <<< "$(_skills_repos)"
    (( ${#repos[@]} )) || return 0
    mkdir -p "$SKILL_CACHE"
    for r in "${repos[@]}"; do sync_git_checkout "$r" "$SKILL_CACHE/${r//\//__}" & done
    wait
}

install_skills() {
    mkdir -p "$HOME/.claude/skills" "$HOME/.codex/skills"
    local explicit_names=$'\n'
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name _ _ <<< "$entry"
        [[ "$name" != "*" ]] && explicit_names+="$name"$'\n'
    done

    local claude_expected="" codex_expected=""
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name source agents <<< "$entry"
        local base_dir; base_dir=$(_resolve_source "$source")
        [[ -d "$base_dir" ]] || { warn "skip $name (source not found: $source)"; continue; }
        [[ "$name" != "*" ]] && _is_manual "$name" && continue

        local -a skill_entries=()
        if [[ "$name" == "*" ]]; then
            if [[ -f "$base_dir/SKILL.md" ]]; then
                skill_entries+=("$(basename "$base_dir"):$base_dir")
            else
                local d
                for d in "$base_dir"/*/; do
                    [[ -f "$d/SKILL.md" ]] || continue
                    d="${d%/}"; local dname="${d##*/}"
                    # Explicit entries override wildcard's agents setting
                    [[ "$explicit_names" == *$'\n'"$dname"$'\n'* ]] && continue
                    _is_manual "$dname" && continue
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
            [[ "$agents" == *claude* ]] && { ensure_symlink "$spath" "$HOME/.claude/skills/$sname"; claude_expected+="$sname"$'\n'; }
            [[ "$agents" == *codex* ]]  && { ensure_symlink "$spath" "$HOME/.codex/skills/$sname";  codex_expected+="$sname"$'\n'; }
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
            _is_manual "$bname" && [[ -e "$entry" ]] && continue
            rm -rf "$entry"; log "clean ${entry/#$HOME/~}"
        done
    done

    # Prune stale cache repos
    [[ -d "$SKILL_CACHE" ]] || return
    local repos; read -ra repos <<< "$(_skills_repos)"
    local cached
    for cached in "$SKILL_CACHE"/*/; do
        [[ -d "$cached" ]] || continue
        local cname="${cached%/}"; cname="${cname##*/}"
        local found=false
        for r in ${repos[@]+"${repos[@]}"}; do
            [[ "${r//\//__}" == "$cname" ]] && { found=true; break; }
        done
        $found || { rm -rf "$cached"; log "clean cache/$cname"; }
    done
}

install_codex_config() {
    local src="$ROOT/agents/codex/config.toml" dest="$HOME/.codex/config.toml"
    [[ -f "$src" ]] || return
    mkdir -p "$HOME/.codex"
    cmp -s "$src" "$dest" 2>/dev/null && return  # skip Python if byte-identical
    # Merge managed keys into existing config (preserves user additions)
    local rc=0
    "$HOME/.venv/bin/python3" - "$src" "$dest" << 'PYEOF' 2>/dev/null || rc=$?
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
    if (( rc == 2 )); then
        log "write ~/.codex/config.toml"
    elif (( rc != 0 )); then
        cp "$src" "$dest"
        log "write ~/.codex/config.toml (fallback copy)"
    fi
}

install_mcp_servers() {
    local has_claude=false has_codex=false
    command -v claude &>/dev/null && has_claude=true
    command -v codex &>/dev/null && has_codex=true
    $has_claude || $has_codex || { warn "neither claude nor codex CLI found"; return; }

    # Skip expensive CLI calls when MCP_SERVERS config hasn't changed
    local stamp_file="$CACHE_DIR/dotfiles-mcp-stamp"
    local fingerprint; fingerprint=$(printf '%s\n' "${MCP_SERVERS[@]}" | md5 2>/dev/null \
        || printf '%s\n' "${MCP_SERVERS[@]}" | md5sum 2>/dev/null | cut -d' ' -f1)
    stamp_fresh "$stamp_file" "$fingerprint" && return

    local claude_mcp_list=""
    $has_claude && { claude_mcp_list="$(claude mcp list 2>/dev/null)" || true; }

    local entry name cmd args
    for entry in "${MCP_SERVERS[@]}"; do
        IFS='|' read -r name cmd args <<< "$entry"
        if $has_claude && ! printf '%s\n' "$claude_mcp_list" | grep -q "^$name:"; then
            claude mcp add --scope user "$name" -- $cmd $args 2>/dev/null \
                && log "add claude/$name" || warn "fail claude/$name"
        fi
        if $has_codex && [[ "$name" != "codex" ]] && ! codex mcp get "$name" &>/dev/null; then
            codex mcp add "$name" -- $cmd $args 2>/dev/null \
                && log "add codex/$name" || warn "fail codex/$name"
        fi
    done

    stamp_write "$stamp_file" "$fingerprint"
}

# ── Skill toggle commands ────────────────────────────────────────

cmd_enable() {
    local name="${1:?usage: dotfiles.sh enable <name>}"
    _is_manual "$name" || { warn "'$name' is not a manual skill"; return 1; }
    local found=false
    # Check explicit entries first
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r ename source agents <<< "$entry"
        [[ "$ename" == "$name" ]] || continue
        _ensure_source "$source"
        local base_dir; base_dir=$(_resolve_source "$source")
        [[ -f "$base_dir/SKILL.md" ]] || { warn "skip $name (no SKILL.md at $source)"; continue; }
        [[ "$agents" == *claude* ]] && ensure_symlink "$base_dir" "$HOME/.claude/skills/$name"
        [[ "$agents" == *codex* ]]  && ensure_symlink "$base_dir" "$HOME/.codex/skills/$name"
        found=true
    done
    # Fall back to wildcard discovery
    if ! $found; then
        for entry in "${SKILLS[@]}"; do
            IFS='|' read -r ename source agents <<< "$entry"
            [[ "$ename" == "*" ]] || continue
            local base_dir; base_dir=$(_resolve_source "$source")
            local skill_dir="$base_dir/$name"
            [[ -f "$skill_dir/SKILL.md" ]] || continue
            [[ "$agents" == *claude* ]] && ensure_symlink "$skill_dir" "$HOME/.claude/skills/$name"
            [[ "$agents" == *codex* ]]  && ensure_symlink "$skill_dir" "$HOME/.codex/skills/$name"
            found=true
        done
    fi
    $found || { warn "skill '$name' not found"; return 1; }
}

cmd_disable() {
    local name="${1:?usage: dotfiles.sh disable <name>}"
    _is_manual "$name" || warn "'$name' is not a manual skill — next run will re-create it"
    local removed=false
    for dir in "$HOME/.claude/skills/$name" "$HOME/.codex/skills/$name"; do
        [[ -L "$dir" ]] && { rm "$dir"; log "removed ${dir/#$HOME/~}"; removed=true; }
    done
    $removed || log "$name is not currently enabled"
}

cmd_skills() {
    printf '\n  %sManual skills%s  (toggle with: ./dotfiles.sh enable/disable <name>)\n\n' "$_CYN" "$_RST"
    local m
    for m in "${MANUAL_SKILLS[@]}"; do
        local status="${_DIM}off${_RST}"
        [[ -L "$HOME/.claude/skills/$m" || -L "$HOME/.codex/skills/$m" ]] && status="on "
        printf '    %-22s %s\n' "$m" "$status"
    done
    printf '\n'
}

# ── Main ─────────────────────────────────────────────────────────

main() {
    cd "$ROOT"
    case "${1:-}" in
        publish) exec "$ROOT/scripts/publish-skills.sh" ;;
        plugins) exec "$ROOT/scripts/install-plugins.sh" ;;
        enable)  cmd_enable "${2:-}"; exit ;;
        disable) cmd_disable "${2:-}"; exit ;;
        skills)  cmd_skills; exit ;;
    esac

    local fp; fp=$(compute_fingerprint)
    if stamp_fresh "$GLOBAL_STAMP" "$fp"; then
        printf '\n  %s🔧 dotfiles%s  up to date %s(%s)%s\n\n' "$_CYN" "$_RST" "$_DIM" "$ROOT" "$_RST"
        exit 0
    fi
    printf '\n  %s🔧 dotfiles%s  %s%s%s\n\n' "$_CYN" "$_RST" "$_DIM" "$ROOT" "$_RST"

    section "Submodules"
    if [[ -f .gitmodules && -s .gitmodules ]]; then
        local _sub_stamp="$CACHE_DIR/dotfiles-submodule-stamp"
        local _sub_fp; _sub_fp=$(md5 < .gitmodules 2>/dev/null || md5sum < .gitmodules 2>/dev/null | cut -d' ' -f1)
        if ! stamp_fresh "$_sub_stamp" "$_sub_fp"; then
            git submodule sync --recursive -q 2>/dev/null || true
            git submodule update --init --recursive -q 2>/dev/null || true
            stamp_write "$_sub_stamp" "$_sub_fp"
        fi
    fi

    # Background: network-dependent tasks
    _fetch_skills_repos &
    local _fetch_pid=$!
    "$ROOT/scripts/install-plugins.sh" &
    local _plugins_pid=$!
    local _mcp_out; _mcp_out=$(mktemp)
    install_mcp_servers > "$_mcp_out" 2>&1 &
    local _mcp_pid=$!

    # Foreground: local-only sections
    section "Links";  install_links
    section "Config"; install_codex_config

    wait "$_fetch_pid" 2>/dev/null || true
    section "Skills"; install_skills

    section "MCP"
    wait "$_mcp_pid" 2>/dev/null || true
    [[ -s "$_mcp_out" ]] && cat "$_mcp_out"
    rm -f "$_mcp_out"

    section "Plugins"
    wait "$_plugins_pid" 2>/dev/null || true

    stamp_write "$GLOBAL_STAMP" "$(compute_fingerprint)"
    printf '\n  ✨ Done. Restart your shell or %ssource ~/.zshrc%s\n\n' "$_DIM" "$_RST"
}

main "$@"
