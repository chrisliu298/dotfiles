#!/usr/bin/env bash
# Verify the Muse column of dotfiles.sh's SKILLS table: muse-selected
# skills are reconciled through `muse skills install` (the skills store owns
# its copy + provenance, so no symlinks land in its personal root), and
# repo-sourced installs that are no longer selected get uninstalled while
# foreign installs are left alone. Uses a stub `muse` on PATH — it only
# records calls; no network, no real Muse state touched (HOME is a tempdir).
# Requires: bash, jq (install_skills reads the store lockfile with jq).

set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-muse-skills.XXXXXX")
trap 'rm -rf "$test_root"' EXIT HUP INT TERM

export HOME="$test_root/home"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
# The DeepSeek column is covered by test-dotfiles-dsh-skills.sh; keep the
# harness home derived from this temp $HOME so no real ~/.dsh is touched.
unset DSH_HOME
calls="$test_root/muse-calls.log"
: > "$calls"

# The main flow fetches skill repos into the cache before install_skills
# runs, so the cache dir exists by then; mirror that precondition here.
mkdir -p "$test_root/bin" "$HOME" "$XDG_CACHE_HOME/skills-src"

# Give the GitHub-sourced pdf skill a cached source so its table entry has a
# resolvable path in the sandbox (assertions below pin down where it may go).
pdf_src="$XDG_CACHE_HOME/skills-src/openai__skills/skills/.curated/pdf"
mkdir -p "$pdf_src"
printf -- '---\nname: pdf\ndescription: sandbox stub\n---\n' > "$pdf_src/SKILL.md"
cat > "$test_root/bin/muse" <<EOF
#!/bin/sh
printf '%s\n' "\$*" >> "$calls"
EOF
chmod +x "$test_root/bin/muse"
export PATH="$test_root/bin:$PATH"

# Pre-seed the store lockfile: one selected skill (must be kept), two stale
# repo-sourced skills (must be pruned; agent-team became claude-only), one
# foreign install (must be left).
muse_skills="$XDG_CONFIG_HOME/muse/skills"
mkdir -p "$muse_skills/.muse"
cat > "$muse_skills/.muse/lock.json" <<EOF
{"version": 1, "skills": {
  "arxiv-reader":  {"source": {"type": "local", "path": "$repo_root/agents/skills/arxiv-reader"}},
  "agent-team":    {"source": {"type": "local", "path": "$repo_root/agents/skills/agent-team"}},
  "cursor-subagent": {"source": {"type": "local", "path": "$repo_root/agents/skills/cursor-subagent"}},
  "foreign-skill": {"source": {"type": "local", "path": "/opt/foreign/foreign-skill"}}
}}
EOF

# Host-local skills in ~/.agents/skills: the claude-only ones must move into
# ~/.claude/skills, lark-* must stay, and an existing Claude copy must win.
seed_skill() { mkdir -p "$1"; printf -- '---\nname: %s\ndescription: sandbox stub\n---\n' "${1##*/}" > "$1/SKILL.md"; }
for name in weekly-report merlin-x merlin-dup lark-y; do seed_skill "$HOME/.agents/skills/$name"; done
seed_skill "$HOME/.claude/skills/merlin-dup"
printf 'claude copy\n' > "$HOME/.claude/skills/merlin-dup/marker"

# dotfiles.sh only runs main when executed, so sourcing loads the tables and
# functions without side effects beyond what install_skills does in $HOME.
# shellcheck disable=SC1091
source "$repo_root/dotfiles.sh"
install_skills >/dev/null

fail() { printf 'FAIL: %s\n' "$1" >&2; printf '%s\n' '--- recorded muse calls ---' >&2; cat "$calls" >&2; exit 1; }

# Each muse-selected universal skill is install-reconciled from its repo
# source with --force (provenance re-recorded, copy refreshed every run).
for name in arxiv-reader; do
    grep -F "skills install $repo_root/agents/skills/$name" "$calls" | grep -q -- '--force' \
        || fail "expected forced muse install for $name from its repo source"
done

# Skills scoped away from Muse (recall's Claude/Codex builds, the claude-only
# skills, Codex's pdf) never reach its store, and the copies Muse discovers
# natively in ~/.claude/skills or ~/.codex/skills are turned off there.
for name in recall agent-team codex-exec gpt-pro pdf weekly-report merlin-x merlin-dup; do
    grep -F "skills install $repo_root/agents/skills/$name" "$calls" >/dev/null \
        && fail "$name must not be installed into Muse"
    grep -qxF "skills disable $name --scope user" "$calls" \
        || fail "expected $name to be disabled in Muse"
done
for name in arxiv-reader; do
    grep -qxF "skills disable $name --scope user" "$calls" \
        && fail "muse-selected $name must stay enabled"
done

# Claude-only host-local skills moved out of ~/.agents/skills; lark-* stayed.
for name in weekly-report merlin-x; do
    [ -f "$HOME/.claude/skills/$name/SKILL.md" ] && [ ! -L "$HOME/.claude/skills/$name" ] \
        || fail "$name should have moved into ~/.claude/skills"
    [ -e "$HOME/.agents/skills/$name" ] && fail "$name must leave ~/.agents/skills"
done
[ -f "$HOME/.agents/skills/lark-y/SKILL.md" ] || fail "lark-* must stay in ~/.agents/skills"
[ -e "$HOME/.claude/skills/lark-y" ] && fail "lark-* must not reach Claude"
[ -f "$HOME/.claude/skills/merlin-dup/marker" ] && [ -d "$HOME/.agents/skills/merlin-dup" ] \
    || fail "an existing ~/.claude/skills copy must not be overwritten"

# pdf is each vendor's own native skill (anthropic for Claude, openai for
# Codex), not a repo-owned one: Codex keeps its symlink, Muse gets nothing.
grep -F "skills install $pdf_src" "$calls" >/dev/null \
    && fail "pdf must not be installed into Muse"
[ -L "$HOME/.codex/skills/pdf" ] || fail "Codex symlink for pdf missing"

# Claude/Codex still get live symlinks; the Muse root gets none (copies only).
[ -L "$HOME/.claude/skills/agent-team" ] || fail "Claude symlink for agent-team missing"
[ -L "$HOME/.codex/skills/arxiv-reader" ] || fail "Codex symlink for arxiv-reader missing"
[ -e "$HOME/.codex/skills/agent-team" ] && fail "agent-team must not be installed into Codex"
[ -z "$(find "$muse_skills" -type l -print -quit)" ] \
    || fail "no symlinks may land in Muse's managed skills root"

# Prune: the stale repo-sourced install is removed; selected and foreign
# installs are untouched.
for name in cursor-subagent agent-team; do
    grep -qx "skills uninstall $name" "$calls" \
        || fail "stale repo-sourced $name install should be uninstalled"
done
grep -q 'skills uninstall arxiv-reader' "$calls" \
    && fail "selected arxiv-reader install must be kept"
grep -q 'skills uninstall foreign-skill' "$calls" \
    && fail "foreign install outside this repo must be left alone"

printf 'ok: Muse SKILLS column reconciles via the skills store\n'
