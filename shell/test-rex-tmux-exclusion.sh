#!/usr/bin/env bash
# Old snapshots and legacy upgrade commands must not resurrect native writers.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
test_root=$(mktemp -d /tmp/rex-tmux-exclusion.XXXXXX)
export TMUX_PERSIST_SOCKET="rex-claude-test-$$"
cleanup() { tmux -L "$TMUX_PERSIST_SOCKET" kill-server 2>/dev/null || true; rm -rf "$test_root"; }
trap cleanup EXIT
export REX_CLAUDE_STATE="$test_root/native" TMUX_PERSIST_STATE="$test_root/tmux" TMUX_PERSIST_CLAUDE_SESSIONS="$test_root/metadata"
mkdir -p "$REX_CLAUDE_STATE/sessions" "$TMUX_PERSIST_STATE" "$TMUX_PERSIST_CLAUDE_SESSIONS"
t() { tmux -L "$TMUX_PERSIST_SOCKET" "$@"; }
t new-session -d -s test-anchor 'sleep 600'
t new-session -d -s renamed-r2v 'sleep 600'
pid=$(t display -p -t '=renamed-r2v:' '#{pane_pid}')
pane=$(t display -p -t '=renamed-r2v:' '#{pane_id}')
start=$(TZ=UTC LC_ALL=C /bin/ps -p "$pid" -o lstart= | xargs)
jq -n --argjson pid "$pid" --arg start "$start" --arg pane "$pane" --arg cwd "$test_root" \
  '{pid:$pid,procStart:$start,tmux:("renamed-r2v:@1."+$pane),cwd:$cwd,sessionId:"same-id"}' > "$TMUX_PERSIST_CLAUDE_SESSIONS/$pid.json"
printf '{"role":"original-r2v","sessionId":"same-id","transport":"rex"}\n' > "$REX_CLAUDE_STATE/sessions/original-r2v.json"
printf 'renamed-r2v\t/tmp\tsame-id\thigh\n' > "$TMUX_PERSIST_STATE/snapshot"
"$repo/shell/tmux-persist" save
[[ ! -s "$TMUX_PERSIST_STATE/snapshot" ]]
if "$repo/shell/tmux-persist" restart renamed-r2v 2>/dev/null; then exit 1; fi
kill -0 "$pid"
t kill-session -t '=renamed-r2v'
printf 'renamed-r2v\t/tmp\tsame-id\thigh\n' > "$TMUX_PERSIST_STATE/snapshot"
"$repo/shell/tmux-persist" restore
if t has-session -t '=renamed-r2v' 2>/dev/null; then exit 1; fi
echo 'PASS: old snapshot, save, renamed identity, legacy restart exclusion'
