#!/usr/bin/env bash
# Sync local skills → their standalone GitHub repos.
# Usage: ./scripts/publish-skills.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PUBLISH_SKILLS=(
    "autoresearch"
    "chatgpt"
    "citation-assistant"
    "deslop"
    "interviewer"
    "last-call"
    "nanorepl"
    "note-gen"
    "prism"
    "prompt-engineer"
    "recall"
    "relay"
    "rlm"
    "vault-linker"
)

# source_path:repo_name (dotfiles path → ~/Developer/GitHub/repo_name)
PUBLISH_CONFIGS=(
    ".config/ghostty:ghostty-config"
)

log()  { printf '     %s\n' "$1"; }
warn() { printf '     %s\n' "$1" >&2; }

dev_dir="$HOME/Developer/GitHub"
skills_dir="$ROOT/agents/extensions/skills"

# ── Configs ──────────────────────────────────────────────────────

for entry in "${PUBLISH_CONFIGS[@]}"; do
    src_rel="${entry%%:*}" repo_name="${entry#*:}"
    src_dir="$ROOT/$src_rel"
    repo_dir="$dev_dir/$repo_name"

    if ! git -C "$repo_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        warn "skip $repo_name (no repo at $repo_dir)"
        continue
    fi
    if [[ ! -d "$src_dir" ]]; then
        warn "skip $repo_name (source missing: $src_rel)"
        continue
    fi

    # Skip dirty repos to avoid overwriting uncommitted work
    if ! git -C "$repo_dir" diff --quiet 2>/dev/null \
        || ! git -C "$repo_dir" diff --cached --quiet 2>/dev/null \
        || [[ -n "$(git -C "$repo_dir" ls-files --others --exclude-standard 2>/dev/null)" ]]; then
        warn "skip $repo_name (repo dirty)"
        continue
    fi

    rsync -a --delete \
        --exclude='.git' --exclude='LICENSE' --exclude='.gitignore' \
        "$src_dir/" "$repo_dir/"

    if git -C "$repo_dir" diff --quiet 2>/dev/null \
        && [[ -z "$(git -C "$repo_dir" ls-files --others --exclude-standard 2>/dev/null)" ]]; then
        : # unchanged
    else
        log "wrote $repo_name"
    fi
done

# ── Skills ───────────────────────────────────────────────────────

for name in "${PUBLISH_SKILLS[@]}"; do
    repo_dir="$dev_dir/$name"
    skill_dir="$skills_dir/$name"

    if ! git -C "$repo_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        warn "skip $name (no repo at $repo_dir)"
        continue
    fi
    if [[ ! -d "$skill_dir" ]]; then
        warn "skip $name (no local skill)"
        continue
    fi

    # Skip dirty repos to avoid overwriting uncommitted work
    if ! git -C "$repo_dir" diff --quiet 2>/dev/null \
        || ! git -C "$repo_dir" diff --cached --quiet 2>/dev/null \
        || [[ -n "$(git -C "$repo_dir" ls-files --others --exclude-standard 2>/dev/null)" ]]; then
        warn "skip $name (repo dirty)"
        continue
    fi

    if [[ "$name" == "relay" ]]; then
        # --copy-unsafe-links materializes symlinks pointing outside the source
        # tree (e.g. references/*.md -> prompt-engineer/references/) into real
        # files, so the published repo stays self-contained.
        mkdir -p "$repo_dir/claude/skills/relay" "$repo_dir/codex/skills/relay" "$repo_dir/scripts"
        rsync -a --delete --copy-unsafe-links --exclude='scripts/' \
            "$skill_dir/claude/" "$repo_dir/claude/skills/relay/"
        rsync -a --delete --copy-unsafe-links --exclude='scripts/' \
            "$skill_dir/codex/" "$repo_dir/codex/skills/relay/"
        rsync -a --delete "$skill_dir/scripts/" "$repo_dir/scripts/"
    else
        rsync -a --delete \
            --exclude='.git' --exclude='LICENSE' \
            --exclude='.gitignore' --exclude='.relay' \
            "$skill_dir/" "$repo_dir/"
    fi

    if git -C "$repo_dir" diff --quiet 2>/dev/null \
        && [[ -z "$(git -C "$repo_dir" ls-files --others --exclude-standard 2>/dev/null)" ]]; then
        : # unchanged
    else
        log "wrote $name"
    fi
done
