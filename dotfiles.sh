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
    "shell/remap-keys:.local/bin/remap-keys"
    "shell/tmux-persist:.local/bin/tmux-persist"
    "shell/codex-traex:.local/bin/codex-traex"
    "shell/cdswap:.local/bin/cdswap"
    "shell/rc-title:.local/bin/rc-title"
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
    "agents/AGENTS.md:.claude/CLAUDE.md"
    "agents/claude/keybindings.json:.claude/keybindings.json"
    "agents/claude/statusline-command.sh:.claude/statusline-command.sh"
    "agents/claude/lang-guard.py:.claude/lang-guard.py"
    "agents/claude/themes/anthropic-dark.json:.claude/themes/anthropic-dark.json"
    "agents/claude/themes/anthropic-light.json:.claude/themes/anthropic-light.json"
    "agents/claude/themes/openai-dark.json:.claude/themes/openai-dark.json"
    "agents/claude/themes/openai-light.json:.claude/themes/openai-light.json"
    "agents/AGENTS.md:.codex/AGENTS.md"
    "agents/codex/themes/openai-dark.tmTheme:.codex/themes/openai-dark.tmTheme"
    "agents/codex/themes/openai-light.tmTheme:.codex/themes/openai-light.tmTheme"
)

# name|source|agents — name * = auto-discover subdirs with SKILL.md
# source: ./path (local), ~/path (host-local, skipped when absent), or owner/repo[/subpath] (GitHub)
SKILLS=(
    # The wildcard installs every skill to Claude, Codex, Muse and DeepSeek Harness; the explicit
    # entries below narrow that (claude-only: codex-exec, agent-team, gpt-pro; recall has a separate
    # build per agent).
    # Claude/Codex/DeepSeek get live symlinks; Muse's store owns its managed personal root,
    # so muse entries are copy-installed via `muse skills install` (see _muse_skill_install).
    # DeepSeek is installed only on hosts where the harness has run (its ~/.dsh exists).
    "*|./agents/skills|claude,codex,muse,deepseek"
    # codex-exec: claude-only caller; Codex is its executor, so it must not get the skill.
    "codex-exec|./agents/skills/codex-exec|claude"
    # agent-team: claude-only caller; the other agents reach it only as dispatched backends.
    "agent-team|./agents/skills/agent-team|claude"
    # gpt-pro: claude-only caller; its scripts dir is on PATH from the Claude copy (shell/.zshenv).
    "gpt-pro|./agents/skills/gpt-pro|claude"
    # recall: one skill name, two harness-specific implementations (like pdf). Both default to
    # their own full transcript store, with an explicit cross-agent mode in a shared entrypoint.
    # agents/skills/recall/ has no SKILL.md, so the wildcard skips it; these two entries install
    # each subdir as `recall`.
    "recall|./agents/skills/recall/claude|claude"
    "recall|./agents/skills/recall/codex|codex"
    # Muse also discovers the Claude/Codex copies natively; install_skills turns off there every
    # skill not selected for Muse.
    # pdf is OpenAI's native skill for Codex (Claude's synced one is off), not repo-owned, so
    # Muse gets no managed copy of it. Muse still discovers the Codex copy natively; keep it
    # off there per host with `muse skills disable pdf --scope user`.
    "pdf|openai/skills/skills/.curated/pdf|codex"
)

# Host-local third-party skills that only Claude may use. Their installers (the legacy Merlin
# bundle script, hand copies) drop them into ~/.agents/skills, which Codex, Muse and DeepSeek
# Harness read natively, so install_skills moves each into ~/.claude/skills.
CLAUDE_ONLY_AGENT_SKILLS=(weekly-report 'merlin-*')

MCP_SERVERS=(  # name|command|args|agents (user-scoped MCP servers; agents: claude,codex or omit for both)
    "chrome-devtools|npx|chrome-devtools-mcp@latest --autoConnect --channel stable --no-usage-statistics|codex"
)

# name|marketplace — Claude plugins installed + enabled at user scope (claude-only)
PLUGINS=()

SKILL_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/skills-src"
# Muse's managed personal skill root, owned by its skills store.
MUSE_SKILLS_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/muse/skills"
# DeepSeek Harness's user skill root; scanned natively alongside ~/.agents/skills.
DSH_HOME_DIR="${DSH_HOME:-$HOME/.dsh}"
DSH_SKILLS_DIR="$DSH_HOME_DIR/skills"
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

# Muse's personal root ($MUSE_SKILLS_DIR) is owned by its skills store,
# which keeps a copy plus provenance for update/uninstall — direct symlinks
# there load in practice but are outside that contract ("provenance missing"
# from store commands). So Muse entries are reconciled through the official
# install command instead of ensure_symlink; every run re-records the source
# and refreshes the copy (--force is what a repeat install requires). Edits
# to a skill therefore reach Muse on the next ./dotfiles.sh run, whose
# fingerprint covers the full tracked diff, not live like the Claude/Codex links.
_muse_skill_install() {
    local spath="$1" sname="$2"
    if muse skills install "$spath" --name "$sname" --force >/dev/null 2>&1; then
        log "muse install $sname"
    else
        warn "muse skills install failed: $sname (from $spath)"
    fi
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

# Has DeepSeek Harness been set up on this host? Its ~/.dsh (or $DSH_HOME) is
# created on first launch; skip the directory entirely rather than seeding it.
_dsh_available() { [[ -d "$DSH_HOME_DIR" ]]; }

_resolve_source() {
    local source="$1"
    if [[ "$source" == ./* ]]; then
        printf '%s' "$ROOT/${source#./}"
    elif [[ "$source" == \~/* ]]; then
        printf '%s' "$HOME/${source#\~/}"
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
    [[ "$source" == ./* || "$source" == \~/* ]] && return
    local _rest="${source#*/}"
    local slug="${source%%/*}/${_rest%%/*}"
    [[ -d "$SKILL_CACHE/${slug//\//__}/.git" ]] && return
    mkdir -p "$SKILL_CACHE"
    sync_git_checkout "$slug" "$SKILL_CACHE/${slug//\//__}"
}

# ── Install functions ────────────────────────────────────────────

# Host-local active theme, decoupled from git. The choice lives in a single
# mode file under XDG state; theme-apply materializes the tools' live config
# from it (ghostty/tmux via optional includes; btop/Starship as generated
# files; Codex by updating only its TUI theme).
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

    # Stage Claude settings, then publish them only after the active theme has
    # been generated. A failed theme build must not leave a dangling selection.
    local claude_src="$ROOT/agents/claude/settings.json" claude_dest="$HOME/.claude/settings.json"
    local claude_stage=""
    if [[ -f "$claude_src" ]]; then
        mkdir -p "$(dirname "$claude_dest")"
        claude_stage="${claude_dest}.install.$$"
        # Merge onto the live file so keys Claude Code writes itself (e.g. /effort's
        # modelSettings) survive; repo values win, and arrays are replaced whole.
        if [[ -f "$claude_dest" && ! -L "$claude_dest" ]] \
            && jq -s '.[0] * .[1]' "$claude_dest" <(sed "s|~/|$HOME/|g" "$claude_src") \
                > "$claude_stage" 2>/dev/null; then
            :
        else
            sed "s|~/|$HOME/|g" "$claude_src" > "$claude_stage"
        fi
    fi
    # The source variants must exist before theme-apply generates anthropic.json and openai.json.
    ensure_symlink "$ROOT/agents/claude/themes/anthropic-dark.json" "$HOME/.claude/themes/anthropic-dark.json"
    ensure_symlink "$ROOT/agents/claude/themes/anthropic-light.json" "$HOME/.claude/themes/anthropic-light.json"
    ensure_symlink "$ROOT/agents/claude/themes/openai-dark.json" "$HOME/.claude/themes/openai-dark.json"
    ensure_symlink "$ROOT/agents/claude/themes/openai-light.json" "$HOME/.claude/themes/openai-light.json"

    # Materialize live config from the repo templates (symlinks may not exist yet).
    if ! BTOP_TEMPLATE="$ROOT/.config/btop/btop.conf.template" \
        STARSHIP_TEMPLATE="$ROOT/.config/starship/starship.toml" \
        CLAUDE_CONFIG="${claude_stage:-$claude_dest}" \
        "$ROOT/shell/theme-apply" "$mode"; then
        [[ -z "$claude_stage" ]] || rm -f "$claude_stage"
        warn "theme-apply failed for mode=$mode"
        return 1
    fi
    log "apply theme: $mode"
    if [[ -n "$claude_stage" ]]; then
        if [[ ! -f "$claude_dest" || -L "$claude_dest" ]] || ! cmp -s "$claude_stage" "$claude_dest"; then
            mv "$claude_stage" "$claude_dest"
            log "write ~/.claude/settings.json"
        else
            rm -f "$claude_stage"
        fi
    fi
}

# Unattended Claude Code sessions (agent-team's claude and ds) often start in a
# session scratchpad under /tmp/claude-<uid>, where an unanswered workspace trust
# dialog stalls them. Trust that root once: it covers every scratchpad below it
# except nested git repositories, which still ask. Claude Code has no setting for
# this; projects[<path>].hasTrustDialogAccepted in ~/.claude.json is the
# documented key (code.claude.com/docs/en/permissions.md).
trust_claude_scratch() {
    local config="$HOME/.claude.json" root tmp
    [[ -f "$config" ]] && command -v jq >/dev/null 2>&1 || return 0
    root="$(cd /tmp && pwd -P)/claude-$(id -u)"
    jq -e --arg p "$root" '.projects[$p].hasTrustDialogAccepted == true' "$config" >/dev/null 2>&1 && return
    tmp=$(mktemp "$config.XXXXXX") || return
    if jq --arg p "$root" '.projects[$p].hasTrustDialogAccepted = true' "$config" > "$tmp"; then
        mv "$tmp" "$config"
        log "trust ${root} in ~/.claude.json"
    else
        rm -f "$tmp"
        warn "could not trust $root in ~/.claude.json"
    fi
}

install_links() {
    local entry
    for entry in "${LINKS[@]}"; do
        local src="$ROOT/${entry%%:*}"
        [[ -e "$src" ]] || { warn "skip ~/${entry#*:} (source missing)"; continue; }
        ensure_symlink "$src" "$HOME/${entry#*:}"
    done
    remove_legacy_delete_hooks
}

# Login agents. Written (not symlinked) because launchd needs this host's
# absolute paths. hidutil remaps reset at reboot, so one re-applies
# shell/remap-keys; tmux sessions die with the machine, so shell/tmux-persist
# snapshots the *-r2v sessions every 5 minutes and restores them at login
# (separate agents, so a session closed on purpose is not revived).
install_launch_agents() {
    [[ "$(uname)" == Darwin ]] || return 0
    install_launch_agent local.remap-keys "<string>$HOME/.local/bin/remap-keys</string>"
    install_launch_agent local.tmux-persist-restore \
        "<string>$HOME/.local/bin/tmux-persist</string><string>restore</string>"
    install_launch_agent local.tmux-persist-save \
        "<string>$HOME/.local/bin/tmux-persist</string><string>save</string>" \
        "<key>StartInterval</key><integer>300</integer>"
}

# install_launch_agent <label> <ProgramArguments strings> [extra plist keys]
install_launch_agent() {
    local label=$1
    local plist="$HOME/Library/LaunchAgents/$label.plist"
    local want
    want=$(cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array>$2</array>
  <key>RunAtLoad</key><true/>${3:+
  $3}
</dict>
</plist>
EOF
)
    [[ -f "$plist" && "$(cat "$plist")" == "$want" ]] && return
    mkdir -p "${plist%/*}"
    printf '%s\n' "$want" > "$plist"
    launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$plist" || warn "launchctl bootstrap $label failed"
    log "load ${plist/#$HOME/~}"
}

remove_legacy_delete_hooks() {
    local dest dir tmp
    for dir in "$HOME/.claude/hooks" "$HOME/.codex/hooks"; do
        if [[ -L "$dir" && "$(readlink "$dir")" == "$ROOT/agents/hooks" ]]; then
            rm "$dir"
            log "unlink ${dir/#$HOME/~}"
        fi
    done

    for dest in "$HOME/.claude/hooks/prevent-catastrophic-delete.sh" \
                "$HOME/.codex/hooks/prevent-catastrophic-delete.sh"; do
        if [[ -L "$dest" && "$(readlink "$dest")" == "$ROOT/agents/hooks/prevent-catastrophic-delete.sh" ]]; then
            rm "$dest"
            log "unlink ${dest/#$HOME/~}"
        fi
    done

    dest="$HOME/.codex/hooks.json"
    if [[ -L "$dest" && "$(readlink "$dest")" == "$ROOT/agents/codex/hooks.json" ]]; then
        rm "$dest"
        log "unlink ${dest/#$HOME/~}"
    fi

    # Remove only this repo's retired hook, preserving host-local hook groups.
    for dest in "$HOME/.claude/settings.json" "$HOME/.codex/hooks.json"; do
        [[ -f "$dest" && ! -L "$dest" ]] || continue
        jq -e '
            type == "object" and
            ((.hooks // {}) | type == "object") and
            ((.hooks.PreToolUse // []) | type == "array") and
            all((.hooks.PreToolUse // [])[];
                type == "object" and
                ((.hooks // []) | type == "array") and
                all((.hooks // [])[]; type == "object"))
        ' "$dest" >/dev/null 2>&1 || {
            warn "skip ${dest/#$HOME/~} hook cleanup (invalid or incompatible schema)"
            continue
        }

        tmp=$(mktemp "${dest}.tmp.XXXXXX")
        jq '
            .hooks.PreToolUse = (
                ((.hooks.PreToolUse // [])
                    | map(.hooks = ((.hooks // []) | map(select((.command // "") | endswith("/hooks/prevent-catastrophic-delete.sh") | not))))
                    | map(select((.hooks | length) > 0)))
            ) |
            if (.hooks.PreToolUse | length) == 0 then del(.hooks.PreToolUse) else . end |
            if (.hooks | length) == 0 then del(.hooks) else . end
        ' "$dest" > "$tmp"
        if cmp -s "$tmp" "$dest"; then
            rm "$tmp"
        else
            chmod 600 "$tmp"
            mv "$tmp" "$dest"
            log "remove retired hook from ${dest/#$HOME/~}"
        fi
    done
}

_skills_repos() {
    local repos=() entry
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r _ source _ <<< "$entry"
        [[ "$source" == ./* || "$source" == \~/* ]] && continue
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

# Move the CLAUDE_ONLY_AGENT_SKILLS out of ~/.agents/skills into ~/.claude/skills, replacing a
# symlink an earlier run left there. An existing directory there is never overwritten.
_claim_claude_only_skills() {
    local pattern src name dest
    for pattern in "${CLAUDE_ONLY_AGENT_SKILLS[@]}"; do
        for src in "$HOME"/.agents/skills/$pattern; do
            [[ -d "$src" && ! -L "$src" && -f "$src/SKILL.md" ]] || continue
            name="${src##*/}" dest="$HOME/.claude/skills/${src##*/}"
            if [[ -e "$dest" && ! -L "$dest" ]]; then
                warn "keep ~/.agents/skills/$name (~/.claude/skills/$name already exists; merge by hand)"
                continue
            fi
            [[ -L "$dest" ]] && rm "$dest"
            mv "$src" "$dest" && log "move ~/.agents/skills/$name → ~/.claude/skills/$name (claude-only)"
        done
    done
}

install_skills() {
    mkdir -p "$HOME/.claude/skills" "$HOME/.codex/skills"
    _claim_claude_only_skills
    # Muse is installed per host (not every machine has it yet); skip its column when absent.
    local muse_available=false
    command -v muse >/dev/null 2>&1 && muse_available=true
    $muse_available || log "muse CLI not found; skipping Muse skills"
    # DeepSeek Harness is likewise per host; its home exists once the app has run.
    local dsh_available=false
    _dsh_available && { dsh_available=true; mkdir -p "$DSH_SKILLS_DIR"; }
    $dsh_available || log "DeepSeek Harness home not found; skipping DeepSeek skills"
    local explicit_names=$'\n'
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name _ _ <<< "$entry"
        [[ "$name" != "*" ]] && explicit_names+="$name"$'\n'
    done

    local claude_expected="" codex_expected="" muse_expected="" dsh_expected=""
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r name source agents <<< "$entry"
        local base_dir; base_dir=$(_resolve_source "$source")
        [[ "$source" == \~/* && ! -d "$base_dir" ]] && continue
        [[ -d "$base_dir" ]] || { warn "skip $name (source not found: $source)"; continue; }

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
            if [[ "$agents" == *claude* && $'\n'"$claude_expected" == *$'\n'"$sname"$'\n'* ]] \
                || [[ "$agents" == *codex* && $'\n'"$codex_expected" == *$'\n'"$sname"$'\n'* ]] \
                || [[ "$agents" == *muse* && $'\n'"$muse_expected" == *$'\n'"$sname"$'\n'* ]]; then
                warn "skip $sname from $source (already provided by an earlier entry)"; continue
            fi
            [[ "$agents" == *claude* ]] && { ensure_symlink "$spath" "$HOME/.claude/skills/$sname"; claude_expected+="$sname"$'\n'; }
            [[ "$agents" == *codex* ]]  && { ensure_symlink "$spath" "$HOME/.codex/skills/$sname";  codex_expected+="$sname"$'\n'; }
            [[ "$agents" == *muse* ]] && $muse_available && { _muse_skill_install "$spath" "$sname"; muse_expected+="$sname"$'\n'; }
            [[ "$agents" == *deepseek* ]] && $dsh_available && { ensure_symlink "$spath" "$DSH_SKILLS_DIR/$sname"; dsh_expected+="$sname"$'\n'; }
        done
    done

    # Clean stale skill symlinks
    local dir expected
    local -a skill_dirs=("$HOME/.claude/skills" "$HOME/.codex/skills")
    $dsh_available && skill_dirs+=("$DSH_SKILLS_DIR")
    for dir in "${skill_dirs[@]}"; do
        [[ -d "$dir" ]] || continue
        # Exact-path match (not substring) so a $HOME containing an agent
        # token can't misclassify a dir and skip its prune set.
        case "$dir" in
            "$HOME/.claude/skills")   expected="$claude_expected" ;;
            "$HOME/.codex/skills")    expected="$codex_expected"  ;;
            "$DSH_SKILLS_DIR")        expected="$dsh_expected"    ;;
        esac
        for entry in "$dir"/*; do
            [[ -L "$entry" ]] || continue
            local bname="${entry##*/}"
            [[ "$bname" == .* ]] && continue
            [[ $'\n'"$expected" == *$'\n'"$bname"$'\n'* ]] && continue
            rm "$entry"; log "clean ${entry/#$HOME/~}"
        done
    done

    # Prune Muse skills this repo installed but no longer selects. The store
    # lockfile records each install's local source, so only entries sourced
    # from this repo or the skill cache are ours to remove — a skill the user
    # installed into Muse by hand is never touched.
    local muse_lock="$MUSE_SKILLS_DIR/.muse/lock.json"
    if $muse_available && [[ -f "$muse_lock" ]] && command -v jq >/dev/null 2>&1; then
        local mid msrc
        while IFS=$'\t' read -r mid msrc; do
            [[ -n "$mid" ]] || continue
            [[ $'\n'"$muse_expected" == *$'\n'"$mid"$'\n'* ]] && continue
            case "$msrc" in "$ROOT"/*|"$SKILL_CACHE"/*) ;; *) continue ;; esac
            muse skills uninstall "$mid" >/dev/null 2>&1 \
                && log "muse uninstall $mid (no longer selected)" || true
        done < <(jq -r '.skills // {} | to_entries[] | select(.value.source.type == "local") | [.key, .value.source.path] | @tsv' "$muse_lock" 2>/dev/null)
    fi
    # Muse also discovers ~/.claude/skills and ~/.codex/skills natively; turn off there every
    # skill the table does not select for Muse, so agent-scoped skills stay scoped.
    if $muse_available; then
        local mskill
        for mskill in "$HOME"/.claude/skills/*/SKILL.md "$HOME"/.codex/skills/*/SKILL.md; do
            [[ -f "$mskill" ]] || continue
            mskill="${mskill%/SKILL.md}" mskill="${mskill##*/}"
            [[ $'\n'"$muse_expected" == *$'\n'"$mskill"$'\n'* ]] && continue
            muse skills disable "$mskill" --scope user >/dev/null 2>&1 || true
        done
    fi

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

# One npm-managed Codex CLI, independent of PATH order and app runtime versions.
setup_codex_cli() {
    command -v npm >/dev/null 2>&1 || { warn "Codex CLI requires npm"; return 127; }
    local prefix cli version
    prefix="$(npm prefix -g)" || return
    cli="$prefix/lib/node_modules/@openai/codex/bin/codex.js"
    version=""
    if [[ -x "$cli" ]]; then
        version="$("$cli" --version)" || return
        version="${version#codex-cli }"
    fi
    if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+ ]] || \
        ! zsh -fc 'autoload -Uz is-at-least; is-at-least 0.159.2 "$1"' -- "$version"; then
        log "install/update npm Codex CLI (requires 0.159.2+)"
        npm install -g @openai/codex@latest || return
        version="$("$cli" --version)" || return
        version="${version#codex-cli }"
        zsh -fc 'autoload -Uz is-at-least; is-at-least 0.159.2 "$1"' -- "$version" || {
            warn "Codex CLI is still too old: $version"
            return 1
        }
    fi
    # Both public entrypoints resolve to this npm package. Leave the app's
    # private runtimes alone; their lifecycle belongs to the desktop app.
    ensure_symlink "$cli" "$HOME/.local/bin/codex"
}

# uv-managed CLI tools: installed once per machine via `uv tool install`
# (not symlinked; credentials/state stay machine-local). Format: "pkg|note".
CLI_TOOLS=(
    "claude-swap|cswap: multi-account switcher for Claude Code"
)

# Homebrew font casks. The SF families ship as .pkg installers that require
# sudo, so install_fonts runs in the foreground (see main) to let the password
# prompt through; already-installed casks are skipped, so it only prompts once.
FONTS=(
    font-sf-pro
    font-noto-sans
)

# Hash the declared `set -g @plugin` set plus the plugin dirs actually on disk,
# so a deleted plugin invalidates the stamp instead of being skipped forever.
# Capture once so the md5sum fallback re-pipes the data rather than hashing
# empty stdin on Linux.
tmux_plugins_fingerprint() {
    local conf="$1" data declared present
    declared=$(awk '/^[ \t]*set(-option)? +-g +@plugin/ {print $4}' "$conf" 2>/dev/null)
    # find, not ls: ls colorizes when CLICOLOR_FORCE is set, and the escape codes
    # both pollute the hash and reorder the sort. LC_ALL=C keeps macOS and Linux
    # collating identically.
    present=$(find "$(dirname "$conf")/plugins" -mindepth 1 -maxdepth 1 -type d 2>/dev/null \
        | sed 's#.*/##' | LC_ALL=C sort)
    data=$(printf '%s\n%s' "$declared" "$present")
    printf '%s' "$data" | md5 2>/dev/null \
        || printf '%s' "$data" | md5sum 2>/dev/null | cut -d' ' -f1
}

# tmux plugins declared as `set -g @plugin` in .config/tmux/tmux.conf and
# installed by TPM. Not symlinked and not tracked (.config/tmux/plugins/.gitignore
# keeps only tpm/ itself), so every machine clones its own copy.
install_tmux_plugins() {
    command -v tmux >/dev/null 2>&1 || { warn "tmux not found; skipping tmux plugins"; return; }
    local tpm_bin="$ROOT/.config/tmux/plugins/tpm/bin/install_plugins"
    [[ -x "$tpm_bin" ]] || { warn "TPM not initialized; skipping tmux plugins"; return; }

    # TPM reads the user-level config, not $ROOT's copy. With no config it finds
    # nothing to install, prints nothing, and still exits 0 -- so check first
    # rather than stamping that silent no-op as a successful install.
    local user_conf="${XDG_CONFIG_HOME:-$HOME/.config}/tmux/tmux.conf"
    [[ -r "$user_conf" ]] || { warn "no tmux.conf at $user_conf; skipping tmux plugins"; return; }

    # TPM parses the conf itself, so this needs no running server.
    local stamp_file="$CACHE_DIR/dotfiles-tmux-plugins-stamp"
    stamp_fresh "$stamp_file" "$(tmux_plugins_fingerprint "$user_conf")" && return

    local out
    if out=$("$tpm_bin" 2>&1); then
        while IFS= read -r line; do [[ -n "$line" ]] && log "$line"; done <<<"$out"
        # Re-hash after installing: the fingerprint covers what's on disk, which
        # the install just changed.
        stamp_write "$stamp_file" "$(tmux_plugins_fingerprint "$user_conf")"
    else
        warn "tmux plugin install failed"
        [[ -n "$out" ]] && warn "$out"
    fi
}

install_tools() {
    command -v uv >/dev/null 2>&1 || { warn "uv not found; skipping CLI tools"; return; }
    local installed spec pkg
    installed=$(uv tool list 2>/dev/null)
    for spec in "${CLI_TOOLS[@]}"; do
        pkg="${spec%%|*}"
        if grep -q "^${pkg} " <<<"$installed"; then
            log "$pkg already installed"
        else
            log "installing $pkg"
            uv tool install -q "$pkg" 2>&1 | tail -1 || warn "failed to install $pkg"
        fi
    done
}

install_fonts() {
    [[ "$(uname -s)" == "Darwin" ]] || return 0
    command -v brew >/dev/null 2>&1 || { warn "brew not found; skipping fonts"; return; }
    local cask
    for cask in "${FONTS[@]}"; do
        if brew list --cask "$cask" >/dev/null 2>&1; then
            log "$cask already installed"
        else
            log "installing $cask (may prompt for sudo)"
            brew install --cask "$cask" >/dev/null 2>&1 || warn "failed to install $cask"
        fi
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
    (( ${#PLUGINS[@]} )) || return 0
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

# ── Skill portability lint ───────────────────────────────────────
# Warn (non-fatal) when a universal (non-claude-only) OWN skill BODY embeds
# harness-specific syntax that silently breaks on Codex. Frontmatter is
# exempt (allowed-tools etc. are additive and ignored off-Claude). Conservative
# by design — flags only the two unambiguous hazards; tool-name degradation
# (AskUserQuestion/Skill) needs human review. See
# agents/skills/references/universal-skill-authoring.md.
lint_skills() {
    local claude_only=$'\n' entry ename _src agents
    for entry in "${SKILLS[@]}"; do
        IFS='|' read -r ename _src agents <<< "$entry"
        [[ "$ename" != "*" && "$agents" == "claude" ]] && claude_only+="$ename"$'\n'
    done
    local d dname m hits=0
    for d in "$ROOT"/agents/skills/*/; do
        d="${d%/}"; dname="${d##*/}"
        [[ -f "$d/SKILL.md" ]] || continue
        [[ "$claude_only" == *$'\n'"$dname"$'\n'* ]] && continue
        m=$(awk 'NR==1&&/^---$/{f=1;next} f&&/^---$/{f=0;next} !f{print FNR": "$0}' "$d/SKILL.md" \
            | grep -E '\$ARGUMENTS|(~|\$HOME|\$\{HOME\})/\.(claude|codex)/skills/' || true)
        [[ -n "$m" ]] || continue
        warn "non-portable syntax in universal skill '$dname' (body):"
        printf '%s\n' "$m" | sed 's/^/        /'
        hits=1
    done
    (( hits )) && warn "fix per agents/skills/references/universal-skill-authoring.md, or scope the skill claude-only"
    return 0
}

# ── Main ─────────────────────────────────────────────────────────

main() {
    cd "$ROOT"
    case "${1:-}" in
        lint)    lint_skills; exit ;;
    esac

    # Host-local installs can drift without changing the repository fingerprint.
    setup_codex_cli
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
    local _tools_out; _tools_out=$(mktemp)
    install_tools > "$_tools_out" 2>&1 &
    local _tools_pid=$!

    # Foreground: local-only sections
    section "Theme"; setup_theme_state
    section "Links";  install_links; install_launch_agents

    # Must start after Links: TPM reads ~/.config/tmux/tmux.conf (the symlink
    # install_links creates), not the repo copy. Launched here rather than with
    # the other network tasks so it still overlaps the waits below.
    local _tmuxp_out; _tmuxp_out=$(mktemp)
    install_tmux_plugins > "$_tmuxp_out" 2>&1 &
    local _tmuxp_pid=$!

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
    # After MCP and plugin registration, whose claude CLI calls also write ~/.claude.json.
    trust_claude_scratch

    section "Tools"
    wait "$_tools_pid" 2>/dev/null || true
    [[ -s "$_tools_out" ]] && cat "$_tools_out"
    rm -f "$_tools_out"

    # Foreground: the SF font .pkg installers need sudo, so this must not be
    # backgrounded (a backgrounded sudo can't read the password from the TTY).
    section "Fonts"; install_fonts

    section "Tmux"
    wait "$_tmuxp_pid" 2>/dev/null || true
    [[ -s "$_tmuxp_out" ]] && cat "$_tmuxp_out"
    rm -f "$_tmuxp_out"

    stamp_write "$GLOBAL_STAMP" "$(compute_fingerprint)"
    printf '\n  ✨ Done. Restart your shell or %ssource ~/.zshrc%s\n\n' "$_DIM" "$_RST"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
