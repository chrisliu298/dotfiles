#!/usr/bin/env bash
# Verify dotfiles.sh's Antigravity (agy) wiring: universal skills are symlinked into
# ~/.gemini/config/skills with agent-team, codex-exec and the agy recall build, gpt-pro stays off every agent, the
# host-local weekly-report/merlin-* skills reach agy from ~/.claude/skills, stale symlinks are pruned,
# hand-installed skill directories are left alone, the repo settings merge onto the
# live settings.json without dropping keys agy wrote, the status line script is linked,
# and a host where agy has never
# run gets no ~/.gemini directory.
# No network and no real agent state: HOME is a tempdir.
# Requires: bash, jq.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-agy.XXXXXX")
trap 'rm -rf "$test_root"' EXIT HUP INT TERM

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# ── Host where agy has run ───────────────────────────────────────
export HOME="$test_root/home"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin
mkdir -p "$HOME/.gemini/antigravity-cli" "$HOME/.gemini/config/skills" "$XDG_CACHE_HOME/skills-src"
ws="$test_root/repo.ws"; git init -q "$ws"; ws_real=$(cd "$ws" && pwd -P)
memdir="$HOME/.claude/projects/$(printf '%s' "$ws_real" | sed 's/[^A-Za-z0-9]/-/g')/memory"
mkdir -p "$memdir"; echo '- [A](a.md) — a' > "$memdir/MEMORY.md"
sub="$ws_real/sub"; mkdir -p "$sub"  # a workspace below the repo root, with a memory of its own
submem="$HOME/.claude/projects/$(printf '%s' "$sub" | sed 's/[^A-Za-z0-9]/-/g')/memory"
mkdir -p "$submem"; echo '- [B](b.md) — b' > "$submem/MEMORY.md"
printf '{"trustedWorkspaces":["/w","%s","%s"],"showFeedbackSurvey":true}\n' "$ws" "$sub" > "$HOME/.gemini/antigravity-cli/settings.json"

stale="$HOME/.gemini/config/skills/retired-skill"
ln -s "$repo_root/agents/skills/retired-skill" "$stale"
mkdir -p "$HOME/.gemini/config/skills/local-handmade"
printf -- '---\nname: local-handmade\ndescription: sandbox stub\n---\n' \
    > "$HOME/.gemini/config/skills/local-handmade/SKILL.md"
# A host-local skill its installer dropped where Codex reads it.
mkdir -p "$HOME/.agents/skills/merlin-hosted"
printf -- '---\nname: merlin-hosted\ndescription: sandbox stub\n---\n' > "$HOME/.agents/skills/merlin-hosted/SKILL.md"

# shellcheck disable=SC1091
source "$repo_root/dotfiles.sh"
install_skills >/dev/null
install_agy_settings >/dev/null

agy_skills="$HOME/.gemini/config/skills"
for name in arxiv-reader lark merlin agent-team codex-exec; do
    link="$agy_skills/$name"
    [ -L "$link" ] || fail "agy symlink for $name missing"
    [ "$(readlink "$link")" = "$repo_root/agents/skills/$name" ] \
        || fail "agy symlink for $name points at $(readlink "$link")"
done
[ "$(readlink "$agy_skills/recall")" = "$repo_root/agents/skills/recall/agy" ] \
    || fail "agy recall should be the agy build, got $(readlink "$agy_skills/recall")"
for name in gpt-pro pdf; do
    if [ -e "$agy_skills/$name" ] || [ -L "$agy_skills/$name" ]; then
        fail "$name must not be installed into agy"
    fi
done
for dir in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
    [ ! -e "$dir/gpt-pro" ] && [ ! -L "$dir/gpt-pro" ] || fail "gpt-pro must be off in $dir"
done
[ -d "$HOME/.claude/skills/merlin-hosted" ] && [ ! -e "$HOME/.agents/skills/merlin-hosted" ] \
    || fail "host-local skill not moved out of ~/.agents/skills"
[ "$(readlink "$agy_skills/merlin-hosted")" = "$HOME/.claude/skills/merlin-hosted" ] \
    || fail "host-local skill not linked for agy"
[ ! -e "$HOME/.codex/skills/merlin-hosted" ] || fail "host-local skill must stay off Codex"
if [ -L "$stale" ]; then fail "stale repo symlink should have been pruned"; fi
[ -d "$agy_skills/local-handmade" ] && [ ! -L "$agy_skills/local-handmade" ] \
    || fail "hand-installed skill directories must be left alone"

settings="$HOME/.gemini/antigravity-cli/settings.json"
[ "$(jq -r '.trustedWorkspaces[0]' "$settings")" = /w ] || fail "merge dropped a key agy wrote"
[ "$(jq '.showFeedbackSurvey' "$settings")" = false ] || fail "repo setting did not win the merge"
[ "$(stat -f %Lp "$settings" 2>/dev/null || stat -c %a "$settings")" = 600 ] || fail "settings.json must stay mode 600"
[ "$(readlink "$HOME/.gemini/antigravity-cli/statusline.sh")" = "$repo_root/agents/agy/statusline.sh" ] \
    || fail "statusline.sh is not linked into the agy home"
[ "$(readlink "$HOME/.gemini/AGENTS.md")" = "$repo_root/agents/AGENTS.md" ] \
    || fail "global rules are not linked as ~/.gemini/AGENTS.md"
[ "$(readlink "$HOME/.gemini/config/hooks.json")" = "$repo_root/agents/agy/hooks.json" ] \
    || fail "hooks.json is not linked into ~/.gemini/config"
rule="$ws_real/.agents/rules/claude-memory.md"
grep -qx 'trigger: always_on' "$rule" && grep -qF "@[Claude project memory](~/${memdir#"$HOME"/}/MEMORY.md)" "$rule" \
    || fail "always-on memory rule missing or wrong: $(cat "$rule" 2>&1)"
grep -qxF '.agents/rules/claude-memory.md' "$ws/.git/info/exclude" || fail "memory rule is not excluded from git"
[ -f "$sub/.agents/rules/claude-memory.md" ] || fail "no memory rule for the subdirectory workspace"
[ -z "$(git -C "$ws" status --porcelain)" ] || fail "memory rule shows up in git status: $(git -C "$ws" status --porcelain)"
install_agy_settings >/dev/null
[ "$(grep -cxF .agents/rules/claude-memory.md "$ws/.git/info/exclude")" = 1 ] && [ "$(grep -cxF sub/.agents/rules/claude-memory.md "$ws/.git/info/exclude")" = 1 ] \
    || fail "exclude entries wrong or added twice: $(cat "$ws/.git/info/exclude")"
[ "$(jq -r '.statusLine.command' "$settings")" = 'bash ~/.gemini/antigravity-cli/statusline.sh' ] \
    || fail "statusLine command missing from merged settings"

# ── Host where agy never ran: nothing is seeded ──────────────────
(
    export HOME="$test_root/home2"
    export XDG_CONFIG_HOME="$HOME/.config"
    export XDG_CACHE_HOME="$HOME/.cache2"
    mkdir -p "$HOME" "$XDG_CACHE_HOME/skills-src"
    # shellcheck disable=SC1091
    source "$repo_root/dotfiles.sh"
    install_skills >/dev/null
    install_agy_settings >/dev/null
    install_links >/dev/null
    [ ! -e "$HOME/.gemini" ] || fail "absent agy home must not be created"
)

printf 'ok: agy skills symlink into ~/.gemini/config/skills and settings merge\n'
