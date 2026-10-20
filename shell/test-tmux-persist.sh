#!/bin/sh
# Offline checks for shell/tmux-persist against fake Claude session files and a
# private tmux server (-L), so real sessions and Claude are never touched.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/tmux-persist-test.XXXXXX")
export TMUX_PERSIST_STATE="$test_root/state" TMUX_PERSIST_CLAUDE_SESSIONS="$test_root/sessions"
export TMUX_PERSIST_SOCKET="tmux-persist-test-$$" TMUX_PERSIST_LAUNCH="echo resumed"
cleanup() {
    tmux -L "$TMUX_PERSIST_SOCKET" kill-server 2>/dev/null || true
    kill "$live_pid" 2>/dev/null || true
    rm -rf "$test_root"
}
trap cleanup EXIT HUP INT TERM
tp="$repo_root/shell/tmux-persist"

fail() { echo "FAIL: $*" >&2; exit 1; }

mkdir -p "$TMUX_PERSIST_STATE" "$TMUX_PERSIST_CLAUDE_SESSIONS"
sleep 600 & live_pid=$!
live_epoch=$(LC_ALL=C /bin/date -j -f '%a %b %d %T %Y' "$(LC_ALL=C /bin/ps -o lstart= -p "$live_pid" | xargs)" +%s)
live_start=$(LC_ALL=C /bin/date -u -r "$live_epoch" '+%a %b %d %T %Y')

# session <pid> <procStart> <tmux> <id>
session() {
    jq -n --argjson p "$1" --arg s "$2" --arg t "$3" --arg i "$4" --arg c "$test_root" \
        '{pid: $p, procStart: $s, tmux: $t, cwd: $c, sessionId: $i}' \
        > "$TMUX_PERSIST_CLAUDE_SESSIONS/$1.json"
}

printf 'keep\n# comment\nother\n' > "$TMUX_PERSIST_STATE/sessions"
session "$live_pid" "$live_start" "keep:@1.%1" id-keep
session "$$" "Thu Jan 01 00:00:00 1970" "other:@2.%2" id-stale   # pid reused: wrong start
session 1 "$live_start" "unlisted:@3.%3" id-unlisted

"$tp" save
[ "$(cat "$TMUX_PERSIST_STATE/snapshot")" = "$(printf 'keep\t%s\tid-keep' "$test_root")" ] \
    || fail "snapshot: $(cat "$TMUX_PERSIST_STATE/snapshot")"

# A listed session whose Claude has exited keeps its last known entry.
rm "$TMUX_PERSIST_CLAUDE_SESSIONS/$live_pid.json"
"$tp" save
grep -q "id-keep" "$TMUX_PERSIST_STATE/snapshot" || fail "entry dropped when Claude was not running"

"$tp" | grep -q "other	(no snapshot)" || fail "status missing unsnapshotted session"

[ "$("$tp" restore)" = "restored keep" ] || fail "restore did not report keep"
tmux -L "$TMUX_PERSIST_SOCKET" has-session -t "=keep" || fail "keep not recreated"
tries=0
until tmux -L "$TMUX_PERSIST_SOCKET" capture-pane -p -t "=keep:" | grep -q "^resumed id-keep"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "resume command not run in pane"
    sleep 0.1
done
[ "$(tmux -L "$TMUX_PERSIST_SOCKET" display -p -t "=keep:" '#{pane_current_path}')" = "$(cd "$test_root" && pwd -P)" ] \
    || fail "pane not in snapshot cwd"

# Running sessions are left alone.
[ -z "$("$tp" restore)" ] || fail "restore touched a running session"

echo "ok"
