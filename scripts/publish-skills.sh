#!/usr/bin/env bash
# Sync local skills → their standalone GitHub repos.
# Usage: ./scripts/publish-skills.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

log()  { printf '     %s\n' "$1"; }
warn() { printf '     %s\n' "$1" >&2; }

dev_dir="$HOME/Developer/GitHub"
skills_dir="$ROOT/agents/extensions/skills"

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
        mkdir -p "$repo_dir/claude/skills/relay" "$repo_dir/codex/skills/relay" "$repo_dir/scripts"
        rsync -a --delete --exclude='scripts/' \
            "$skill_dir/claude/" "$repo_dir/claude/skills/relay/"
        rsync -a --delete --exclude='scripts/' \
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
