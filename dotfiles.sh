#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Declarative tables ───────────────────────────────────────────

LINKS=(
    "shell/.aliases:.aliases"
    "shell/.functions:.functions"
    "shell/.zshenv:.zshenv"
    "shell/.zshrc:.zshrc"
    "shell/theme-apply:.local/bin/theme-apply"
    ".config/starship:.config/starship"
    # btop has no config include and rewrites its own config, so its live
    # ~/.config/btop/btop.conf is host-local (generated, outside git). Only the
    # tracked themes/ and the template are symlinked in; see setup_theme_state.
    ".config/btop/themes:.config/btop/themes"
    ".config/btop/btop.conf.template:.config/btop/btop.conf.template"
    ".config/fastfetch:.config/fastfetch"
    ".config/nvim:.config/nvim"
    ".config/tmux:.config/tmux"
    ".config/ghostty:.config/ghostty"
    "agents/claude/CLAUDE.md:.claude/CLAUDE.md"
    "agents/claude/keybindings.json:.claude/keybindings.json"
    "agents/claude/statusline-command.sh:.claude/statusline-command.sh"
    "agents/codex/AGENTS.md:.codex/AGENTS.md"
    "agents/grok/AGENTS.md:.grok/AGENTS.md"
    "agents/pi/AGENTS.md:.pi/agent/AGENTS.md"
    "agents/pi/settings.json:.pi/agent/settings.json"
)

# name|source|agents — name * = auto-discover subdirs with SKILL.md
# source: ./path (local) or owner/repo[/subpath] (GitHub)
SKILLS=(
    # grok and pi both mirror the Codex set (grok dispatches as a relay/prism target;
    # pi is a standalone harness that reads ~/.pi/agent/skills/), including side-effecting
    # skills like gpt-pro-relay/push — those are allowed. Only the claude-only entries below
    # (relay, prism, keep-warm, crons, goal-loop, recall, codex-first, skill-creator) are left
    # off grok/pi; relay and prism are additionally blocked from being triggered on grok
    # (RELAY_PEER guard + PATH scrub of both script dirs + the GROK_CLAUDE_*_ENABLED=false
    # compat suite set in .zshenv and the relay grok transport).
    "*|./agents/extensions/skills|claude,codex,grok,pi"
    # Relay: claude-only caller; targets Codex, Grok, GLM, Kimi, DeepSeek, and MiMo via the script
    "relay|./agents/extensions/skills/relay|claude"
    # keep-warm relies on Claude-only scheduling tools (CronCreate, ScheduleWakeup)
    "keep-warm|./agents/extensions/skills/keep-warm|claude"
    # crons: claude-only durable manifest + re-arm for the recurring /loop + CronCreate fleet
    # (CronCreate/CronList/CronDelete are Claude-only); preparer-not-actuator, no docmaint freshness gate
    "crons|./agents/extensions/skills/crons|claude"
    # prism: claude-only caller (dispatches parallax to Codex + Grok + GLM + Kimi + DeepSeek + MiMo via relay)
    "prism|./agents/extensions/skills/prism|claude"
    # goal-loop: default review backend is prism (claude-only); built on the Skill/AskUserQuestion
    # tooling. Off-Claude it only degrades to external/local/none, so keep it claude-only.
    "goal-loop|./agents/extensions/skills/goal-loop|claude"
    # recall: claude-only; searches THIS project's past Claude transcripts (~/.claude/projects) for
    # an earlier user statement. The store is Claude-specific, so it has no meaning on Codex/Grok.
    "recall|./agents/extensions/skills/recall|claude"
    # codex-first: claude-only routing skill — delegates hands-on work to `codex exec` while Claude
    # specs + reviews; a Codex/Grok session self-delegating to Codex is meaningless. MANUAL (below),
    # so it's off until `./dotfiles.sh enable codex-first`. The explicit entry overrides the wildcard.
    "codex-first|./agents/extensions/skills/codex-first|claude"
    "defuddle|kepano/obsidian-skills/skills/defuddle|claude,codex,grok,pi"
    "humanizer|blader/humanizer|claude,codex,grok,pi"
    "pdf|anthropics/skills/skills/pdf|claude"
    "skill-creator|anthropics/skills/skills/skill-creator|claude"
    "pdf|openai/skills/skills/.curated/pdf|codex,grok,pi"
)

# Skills not auto-installed (opt-in). Toggle with: ./dotfiles.sh enable/disable <name>.
MANUAL_SKILLS=(
    autoresearch
    codex-first
    deslop
    interviewer
    prompt-engineer
)

# Which manual skills are currently enabled — a committed declarative set, one
# name per line ('#' comments / blank lines ignored; empty = all off). Every
# ./dotfiles.sh run enforces it (symlink the listed, prune the rest), and
# enable/disable rewrite it. Since dfs runs `git pull && ./dotfiles.sh` on each
# peer, a commit + dfs propagates the set to every machine — no per-host toggling.
MANUAL_ENABLED_FILE="$ROOT/agents/extensions/manual-skills.enabled"

MCP_SERVERS=(  # name|command|args|agents (user-scoped MCP servers; agents: claude,codex or omit for both)
    "chrome-devtools|npx|chrome-devtools-mcp@latest --autoConnect --channel stable --no-usage-statistics|codex"
)

# name|marketplace — Claude plugins installed + enabled at user scope (claude-only)
PLUGINS=(
    "code-simplifier|claude-plugins-official"
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
    # Hash HEAD + tracked diff content + status so edits inside already-dirty
    # files still invalidate the cache stamp. Capture once so the md5sum
    # fallback re-pipes the data instead of hashing empty stdin on Linux.
    local data
    data=$({ git -C "$ROOT" rev-parse HEAD 2>/dev/null
             git -C "$ROOT" status --porcelain=v1 2>/dev/null
             git -C "$ROOT" diff --no-ext-diff --no-color HEAD -- . 2>/dev/null; })
    printf '%s' "$data" | md5 2>/dev/null \
        || printf '%s' "$data" | md5sum 2>/dev/null | cut -d' ' -f1
}

# Skip fetch if FETCH_HEAD was updated less than 300s ago
_fetch_fresh() {
    local fh="$1/.git/FETCH_HEAD"
    [[ -f "$fh" ]] || return 1
    local mtime; mtime=$(stat -c %Y "$fh" 2>/dev/null || /usr/bin/stat -f %m "$fh" 2>/dev/null) || return 1
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

# Is manual skill $1 enabled in the committed set?
_manual_enabled() {
    [[ -f "$MANUAL_ENABLED_FILE" ]] && grep -qxF "$1" "$MANUAL_ENABLED_FILE"
}

# Record manual skill $1 as on|off in the committed set (sorted, de-duped, header
# preserved). Caller commits + runs dfs to propagate the change to every machine.
_manual_set_state() {
    local name="$1" state="$2" data
    mkdir -p "$(dirname "$MANUAL_ENABLED_FILE")"
    [[ -f "$MANUAL_ENABLED_FILE" ]] || : > "$MANUAL_ENABLED_FILE"
    data=$(grep -vE '^[[:space:]]*(#|$)' "$MANUAL_ENABLED_FILE" 2>/dev/null | grep -vxF "$name" || true)
    [[ "$state" == on ]] && data=$(printf '%s\n%s' "$data" "$name")
    data=$(printf '%s\n' "$data" | grep -vE '^[[:space:]]*$' | LC_ALL=C sort -u || true)
    {
        printf '# Enabled manual skills, one per line (committed; dfs propagates). Empty = all off.\n'
        printf '# Toggle with ./dotfiles.sh enable/disable <name>; enforced on every ./dotfiles.sh run.\n'
        [[ -n "$data" ]] && printf '%s\n' "$data"
    } > "$MANUAL_ENABLED_FILE"
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

# Host-local active theme, decoupled from git. The choice lives in a single
# mode file under XDG state; theme-apply materializes the four tools' live config
# from it (ghostty/tmux via optional includes; btop/Starship as generated files).
# MUST run before install_links: it converts a legacy whole-dir btop symlink into
# a real dir so the per-file btop links below don't rm -rf through the symlink
# into the repo. Idempotent and safe to re-run on every host.
setup_theme_state() {
    local state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles-theme"
    local mode_file="$state_dir/mode" mode

    # Convert a legacy `~/.config/btop -> repo` whole-dir symlink into a real dir.
    if [[ -L "$HOME/.config/btop" ]]; then
        rm "$HOME/.config/btop"
        log "unlink legacy ~/.config/btop symlink (now host-local)"
    fi
    mkdir -p "$HOME/.config/btop" "$state_dir"

    # Seed the mode once (default dark); respect a value captured during migration.
    if [[ -f "$mode_file" ]]; then
        mode="$(cat "$mode_file")"
        [[ "$mode" == light || "$mode" == dark ]] || mode="dark"
    else
        mode="dark"
        printf '%s\n' "$mode" > "$mode_file"
        log "seed theme state: mode=$mode (run 'theme light' to switch)"
    fi

    # Materialize live config from the repo templates (symlinks may not exist yet).
    BTOP_TEMPLATE="$ROOT/.config/btop/btop.conf.template" \
    STARSHIP_TEMPLATE="$ROOT/.config/starship/starship.toml" \
        "$ROOT/shell/theme-apply" "$mode" \
        && log "apply theme: $mode" \
        || warn "theme-apply failed for mode=$mode"
}

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
    mkdir -p "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.grok/skills" "$HOME/.pi/agent/skills"
    local explicit_names=$'\n'
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name _ _ <<< "$entry"
        [[ "$name" != "*" ]] && explicit_names+="$name"$'\n'
    done

    local claude_expected="" codex_expected="" grok_expected="" pi_expected=""
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name source agents <<< "$entry"
        local base_dir; base_dir=$(_resolve_source "$source")
        [[ -d "$base_dir" ]] || { warn "skip $name (source not found: $source)"; continue; }
        [[ "$name" != "*" ]] && _is_manual "$name" && ! _manual_enabled "$name" && continue

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
                    # Manual skills install only when enabled in the committed set
                    _is_manual "$dname" && ! _manual_enabled "$dname" && continue
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
            [[ "$agents" == *grok* ]]   && { ensure_symlink "$spath" "$HOME/.grok/skills/$sname";   grok_expected+="$sname"$'\n'; }
            [[ "$agents" == *pi* ]]     && { ensure_symlink "$spath" "$HOME/.pi/agent/skills/$sname"; pi_expected+="$sname"$'\n'; }
        done
    done

    # Clean stale skill symlinks
    local dir expected
    for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.grok/skills" "$HOME/.pi/agent/skills"; do
        [[ -d "$dir" ]] || continue
        # Exact-path match (not substring) so a $HOME containing an agent
        # token can't misclassify a dir and skip its prune set.
        case "$dir" in
            "$HOME/.claude/skills")   expected="$claude_expected" ;;
            "$HOME/.codex/skills")    expected="$codex_expected"  ;;
            "$HOME/.grok/skills")     expected="$grok_expected"   ;;
            "$HOME/.pi/agent/skills") expected="$pi_expected"     ;;
        esac
        for entry in "$dir"/*; do
            [[ -L "$entry" ]] || continue
            local bname="${entry##*/}"
            [[ "$bname" == .* ]] && continue
            # Enabled manual skills are in "$expected" (kept above); a manual skill
            # absent from the committed set falls through here and is pruned.
            [[ $'\n'"$expected" == *$'\n'"$bname"$'\n'* ]] && continue
            rm "$entry"; log "clean ${entry/#$HOME/~}"
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

    local entry name cmd args agents
    for entry in "${MCP_SERVERS[@]}"; do
        IFS='|' read -r name cmd args agents <<< "$entry"
        [[ -z "$agents" ]] && agents="claude,codex"
        if $has_claude && [[ ",$agents," == *,claude,* ]] \
            && ! printf '%s\n' "$claude_mcp_list" | grep -q "^$name:"; then
            claude mcp add --scope user "$name" -- $cmd $args 2>/dev/null \
                && log "add claude/$name" || warn "fail claude/$name"
        fi
        if $has_codex && [[ ",$agents," == *,codex,* ]] && [[ "$name" != "codex" ]] \
            && ! codex mcp get "$name" &>/dev/null; then
            codex mcp add "$name" -- $cmd $args 2>/dev/null \
                && log "add codex/$name" || warn "fail codex/$name"
        fi
    done

    stamp_write "$stamp_file" "$fingerprint"
}

install_plugins() {
    command -v claude &>/dev/null || { warn "claude CLI not found — skipping plugins"; return; }

    # Skip CLI calls when PLUGINS config hasn't changed
    local stamp_file="$CACHE_DIR/dotfiles-plugins-stamp"
    local fingerprint; fingerprint=$(printf '%s\n' "${PLUGINS[@]}" | md5 2>/dev/null \
        || printf '%s\n' "${PLUGINS[@]}" | md5sum 2>/dev/null | cut -d' ' -f1)
    stamp_fresh "$stamp_file" "$fingerprint" && return

    local list; list="$(claude plugin list 2>/dev/null)" || true
    local markets; markets="$(claude plugin marketplace list 2>/dev/null)" || true

    local entry name mkt full
    for entry in "${PLUGINS[@]}"; do
        IFS='|' read -r name mkt <<< "$entry"
        full="$name@$mkt"
        # Ensure the marketplace is configured (only the official one is auto-added)
        if ! printf '%s\n' "$markets" | grep -q "❯ $mkt$"; then
            [[ "$mkt" == "claude-plugins-official" ]] \
                && claude plugin marketplace add anthropics/claude-plugins-official >/dev/null 2>&1 || true
        fi
        # Already installed at user scope and enabled? nothing to do
        if printf '%s\n' "$list" | awk -v t="$full" '
            /❯ / { cur=$2; scope="" }
            /Scope:/ { scope=$2 }
            /Status:/ { if (cur==t && scope=="user" && /enabled/) f=1 }
            END { exit(f?0:1) }'; then
            continue
        fi
        claude plugin install "$full" --scope user >/dev/null 2>&1 || true
        claude plugin enable "$full" --scope user >/dev/null 2>&1 || true
        log "enable $name"
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
        [[ "$agents" == *grok* ]]   && ensure_symlink "$base_dir" "$HOME/.grok/skills/$name"
        [[ "$agents" == *pi* ]]     && ensure_symlink "$base_dir" "$HOME/.pi/agent/skills/$name"
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
            [[ "$agents" == *grok* ]]   && ensure_symlink "$skill_dir" "$HOME/.grok/skills/$name"
            [[ "$agents" == *pi* ]]     && ensure_symlink "$skill_dir" "$HOME/.pi/agent/skills/$name"
            found=true
        done
    fi
    $found || { warn "skill '$name' not found"; return 1; }
    _manual_set_state "$name" on
    log "enabled '$name' in the committed set — commit + run dfs to propagate"
}

cmd_disable() {
    local name="${1:?usage: dotfiles.sh disable <name>}"
    _is_manual "$name" || warn "'$name' is not a manual skill — next run will re-create it"
    local removed=false
    for dir in "$HOME/.claude/skills/$name" "$HOME/.codex/skills/$name" "$HOME/.grok/skills/$name" "$HOME/.pi/agent/skills/$name"; do
        [[ -L "$dir" ]] && { rm "$dir"; log "removed ${dir/#$HOME/~}"; removed=true; }
    done
    if _is_manual "$name"; then
        _manual_set_state "$name" off
        log "disabled '$name' in the committed set — commit + run dfs to propagate"
    fi
    $removed || log "$name is not currently enabled"
}

cmd_skills() {
    printf '\n  %sManual skills%s  (toggle with: ./dotfiles.sh enable/disable <name>)\n\n' "$_CYN" "$_RST"
    local m
    for m in "${MANUAL_SKILLS[@]}"; do
        local status="${_DIM}off${_RST}"
        [[ -L "$HOME/.claude/skills/$m" || -L "$HOME/.codex/skills/$m" || -L "$HOME/.grok/skills/$m" || -L "$HOME/.pi/agent/skills/$m" ]] && status="on "
        printf '    %-22s %s\n' "$m" "$status"
    done
    printf '\n'
}

# ── Skill portability lint ───────────────────────────────────────
# Warn (non-fatal) when a universal (non-claude-only) OWN skill BODY embeds
# harness-specific syntax that silently breaks on Codex/Grok. Frontmatter is
# exempt (allowed-tools etc. are additive and ignored off-Claude). Conservative
# by design — flags only the two unambiguous hazards; tool-name degradation
# (AskUserQuestion/Skill) needs human review. See
# agents/extensions/references/universal-skill-authoring.md.
lint_skills() {
    local claude_only=$'\n' entry ename _src agents
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r ename _src agents <<< "$entry"
        [[ "$ename" != "*" && "$agents" == "claude" ]] && claude_only+="$ename"$'\n'
    done
    local d dname m hits=0
    for d in "$ROOT"/agents/extensions/skills/*/; do
        d="${d%/}"; dname="${d##*/}"
        [[ -f "$d/SKILL.md" ]] || continue
        [[ "$claude_only" == *$'\n'"$dname"$'\n'* ]] && continue
        m=$(awk 'NR==1&&/^---$/{f=1;next} f&&/^---$/{f=0;next} !f{print FNR": "$0}' "$d/SKILL.md" \
            | grep -E '\$ARGUMENTS|~/\.(claude|codex|grok)/skills/' || true)
        [[ -n "$m" ]] || continue
        warn "non-portable syntax in universal skill '$dname' (body):"
        printf '%s\n' "$m" | sed 's/^/        /'
        hits=1
    done
    (( hits )) && warn "fix per agents/extensions/references/universal-skill-authoring.md, or scope the skill claude-only"
    # docmaint + agentdocs statuses propagate: fatal for `./dotfiles.sh lint`, advisory in a full run
    local _dm=0 _ad=0
    lint_docmaint  || _dm=$?
    lint_agentdocs || _ad=$?
    return $(( _dm || _ad ))
}

# ── docmaint drift-guard ─────────────────────────────────────────
# The todo/exec-status/mental-seal skills each ship a copy of docmaint.py that MUST be
# byte-identical except the one `DOC = "..."` line (todo|status|seal). Catch drift (a fix
# landing in one copy but not the others) and a DOC value that doesn't match its skill dir.
lint_docmaint() {
    local -a copies=(
        "todo:agents/extensions/skills/todo/scripts/docmaint.py"
        "status:agents/extensions/skills/exec-status/scripts/docmaint.py"
        "seal:agents/extensions/skills/mental-seal/scripts/docmaint.py"
    )
    local entry want path norm prev="" prev_name="" doc rc=0
    for entry in "${copies[@]}"; do
        want="${entry%%:*}"; path="${entry#*:}"
        if [[ ! -f "$ROOT/$path" ]]; then warn "docmaint: missing copy $path"; rc=1; continue; fi
        doc=$(sed -nE 's/^DOC = "(todo|status|seal)"$/\1/p' "$ROOT/$path" | head -1)
        [[ "$doc" == "$want" ]] || { warn "docmaint: $path has DOC=\"$doc\", expected \"$want\""; rc=1; }
        norm=$(sed -E 's/^DOC = "(todo|status|seal)"$/DOC = "X"/' "$ROOT/$path" | shasum | cut -d' ' -f1)
        if [[ -n "$prev" && "$norm" != "$prev" ]]; then
            warn "docmaint: $path drifted from $prev_name (copies must be identical except the DOC line) — re-sync them"
            rc=1
        fi
        prev="$norm"; prev_name="$path"
    done
    return "$rc"
}

# ── agent-doc identity-guard ─────────────────────────────────────
# The four global instruction files (claude/CLAUDE.md, codex/AGENTS.md, grok/AGENTS.md,
# pi/AGENTS.md) are one canonical text copied verbatim to all four paths — byte-identical,
# no per-agent deltas (a de-formatted, agent-read doc; effectiveness parity verified by the
# instruction-following harness in agents/eval/). Assert that identity; any diff means one
# copy was edited without propagating. To change them: edit one, copy to the other three,
# commit together.
lint_agentdocs() {
    local -a docs=(
        "agents/claude/CLAUDE.md"
        "agents/codex/AGENTS.md"
        "agents/grok/AGENTS.md"
        "agents/pi/AGENTS.md"
    )
    local ref="${docs[0]}" f rc=0
    if [[ ! -f "$ROOT/$ref" ]]; then warn "agentdocs: missing canonical $ref"; return 1; fi
    for f in "${docs[@]:1}"; do
        if [[ ! -f "$ROOT/$f" ]]; then warn "agentdocs: missing copy $f"; rc=1; continue; fi
        if ! diff -q "$ROOT/$ref" "$ROOT/$f" >/dev/null 2>&1; then
            warn "agentdocs: $f differs from $ref (the four must be byte-identical) — re-copy the canonical text"
            rc=1
        fi
    done
    return "$rc"
}

# ── Main ─────────────────────────────────────────────────────────

main() {
    cd "$ROOT"
    case "${1:-}" in
        enable)  cmd_enable "${2:-}"; exit ;;
        disable) cmd_disable "${2:-}"; exit ;;
        skills)  cmd_skills; exit ;;
        lint)    lint_skills; exit ;;
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
    local _mcp_out; _mcp_out=$(mktemp)
    install_mcp_servers > "$_mcp_out" 2>&1 &
    local _mcp_pid=$!
    local _plugins_out; _plugins_out=$(mktemp)
    install_plugins > "$_plugins_out" 2>&1 &
    local _plugins_pid=$!

    # Foreground: local-only sections
    section "Theme"; setup_theme_state
    section "Links";  install_links

    wait "$_fetch_pid" 2>/dev/null || true
    section "Skills"; install_skills; lint_skills

    section "MCP"
    wait "$_mcp_pid" 2>/dev/null || true
    [[ -s "$_mcp_out" ]] && cat "$_mcp_out"
    rm -f "$_mcp_out"

    section "Plugins"
    wait "$_plugins_pid" 2>/dev/null || true
    [[ -s "$_plugins_out" ]] && cat "$_plugins_out"
    rm -f "$_plugins_out"

    stamp_write "$GLOBAL_STAMP" "$(compute_fingerprint)"
    printf '\n  ✨ Done. Restart your shell or %ssource ~/.zshrc%s\n\n' "$_DIM" "$_RST"
}

main "$@"
