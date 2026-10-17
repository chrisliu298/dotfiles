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

# Pre-seed the store lockfile: one selected skill (must be kept), one stale
# repo-sourced skill (must be pruned), one foreign install (must be left).
muse_skills="$XDG_CONFIG_HOME/muse/skills"
mkdir -p "$muse_skills/.muse"
cat > "$muse_skills/.muse/lock.json" <<EOF
{"version": 1, "skills": {
  "agent-team":    {"source": {"type": "local", "path": "$repo_root/agents/skills/agent-team"}},
  "cursor-subagent": {"source": {"type": "local", "path": "$repo_root/agents/skills/cursor-subagent"}},
  "foreign-skill": {"source": {"type": "local", "path": "/opt/foreign/foreign-skill"}}
}}
EOF

# dotfiles.sh only runs main when executed, so sourcing loads the tables and
# functions without side effects beyond what install_skills does in $HOME.
# shellcheck disable=SC1091
source "$repo_root/dotfiles.sh"
install_skills >/dev/null

fail() { printf 'FAIL: %s\n' "$1" >&2; printf '%s\n' '--- recorded muse calls ---' >&2; cat "$calls" >&2; exit 1; }

# Each muse-selected universal skill is install-reconciled from its repo
# source with --force (provenance re-recorded, copy refreshed every run).
for name in agent-team arxiv-reader gpt-pro push; do
    grep -F "skills install $repo_root/agents/skills/$name" "$calls" | grep -q -- '--force' \
        || fail "expected forced muse install for $name from its repo source"
done

# recall has Claude and Codex builds only; neither reaches Muse, and the
# copies Muse discovers natively are turned off there.
grep -F "skills install $repo_root/agents/skills/recall" "$calls" >/dev/null \
    && fail "recall must not be installed into Muse"
grep -qxF "skills disable recall --scope user" "$calls" \
    || fail "expected recall to be disabled in Muse"

# Skills without the muse token never reach the Muse store: the claude-only
# orchestrators.
for name in relay prism; do
    grep -F "skills install $repo_root/agents/skills/$name" "$calls" >/dev/null \
        && fail "$name must not be installed into Muse"
done

# pdf is each vendor's own native skill (anthropic for Claude, openai for
# Codex), not a repo-owned one: Codex keeps its symlink, Muse gets nothing.
grep -F "skills install $pdf_src" "$calls" >/dev/null \
    && fail "pdf must not be installed into Muse"
[ -L "$HOME/.codex/skills/pdf" ] || fail "Codex symlink for pdf missing"

# Claude/Codex still get live symlinks; the Muse root gets none (copies only).
[ -L "$HOME/.claude/skills/agent-team" ] || fail "Claude symlink for agent-team missing"
[ -L "$HOME/.codex/skills/agent-team" ]  || fail "Codex symlink for agent-team missing"
[ -z "$(find "$muse_skills" -type l -print -quit)" ] \
    || fail "no symlinks may land in Muse's managed skills root"

# Prune: the stale repo-sourced install is removed; selected and foreign
# installs are untouched.
grep -qx 'skills uninstall cursor-subagent' "$calls" \
    || fail "stale repo-sourced cursor-subagent install should be uninstalled"
grep -q 'skills uninstall agent-team' "$calls" \
    && fail "selected agent-team install must be kept"
grep -q 'skills uninstall foreign-skill' "$calls" \
    && fail "foreign install outside this repo must be left alone"

printf 'ok: Muse SKILLS column reconciles via the skills store\n'
