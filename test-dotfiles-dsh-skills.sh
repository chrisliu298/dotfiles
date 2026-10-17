#!/usr/bin/env bash
# Verify the DeepSeek Harness column of dotfiles.sh's SKILLS table: universal
# skills are symlinked into ~/.dsh/skills (the harness's user skill root),
# claude-only skills stay out, stale symlinks are pruned, hand-installed skill
# directories are left alone, and a host without ~/.dsh gets no directory.
# No network and no real agent state: HOME is a tempdir.
# Requires: bash.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-dsh-skills.XXXXXX")
trap 'rm -rf "$test_root"' EXIT HUP INT TERM

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# ── Host with DeepSeek Harness set up ────────────────────────────
export HOME="$test_root/home"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
# Derive the harness home from $HOME; keep muse (a real CLI on some hosts) out
# of this test so only the DeepSeek column runs.
unset DSH_HOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
mkdir -p "$HOME/.dsh/skills" "$XDG_CACHE_HOME/skills-src"

# Pre-seed one stale repo symlink (must be pruned) and one regular directory
# the user installed by hand (must survive: prune only touches symlinks).
stale="$HOME/.dsh/skills/cursor-subagent"
ln -s "$repo_root/agents/skills/cursor-subagent" "$stale"
mkdir -p "$HOME/.dsh/skills/local-handmade"
printf -- '---\nname: local-handmade\ndescription: sandbox stub\n---\n' \
    > "$HOME/.dsh/skills/local-handmade/SKILL.md"

# shellcheck disable=SC1091
source "$repo_root/dotfiles.sh"
install_skills >/dev/null

dsh_skills="$HOME/.dsh/skills"
for name in arxiv-reader; do
    link="$dsh_skills/$name"
    [ -L "$link" ] || fail "DeepSeek symlink for $name missing"
    [ "$(readlink "$link")" = "$repo_root/agents/skills/$name" ] \
        || fail "DeepSeek symlink for $name points at $(readlink "$link")"
done

for name in agent-team codex-exec gpt-pro relay prism recall; do
    if [ -e "$dsh_skills/$name" ] || [ -L "$dsh_skills/$name" ]; then
        fail "$name must not be installed into DeepSeek"
    fi
done

if [ -L "$stale" ]; then fail "stale repo symlink should have been pruned"; fi
[ -d "$dsh_skills/local-handmade" ] && [ ! -L "$dsh_skills/local-handmade" ] \
    || fail "hand-installed skill directories must be left alone"

# ── Host without DeepSeek Harness: no directory is seeded ────────
(
    export HOME="$test_root/home2"
    export XDG_CONFIG_HOME="$HOME/.config"
    export XDG_CACHE_HOME="$HOME/.cache2"
    unset DSH_HOME
    mkdir -p "$HOME" "$XDG_CACHE_HOME/skills-src"
    # shellcheck disable=SC1091
    source "$repo_root/dotfiles.sh"
    install_skills >/dev/null
    [ ! -e "$HOME/.dsh" ] || fail "absent DeepSeek home must not be created"
)

printf 'ok: DeepSeek Harness SKILLS column symlinks into ~/.dsh/skills\n'
