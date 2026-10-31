#!/bin/sh
# Offline checks for shell/tmux-persist against fake Claude session files and a
# private tmux server (-L), so real sessions and Claude are never touched.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/tmux-persist-test.XXXXXX")
export TMUX_PERSIST_STATE="$test_root/state" TMUX_PERSIST_CLAUDE_SESSIONS="$test_root/sessions"
export TMUX_PERSIST_SOCKET="tmux-persist-test-$$" TMUX_PERSIST_LAUNCH="echo resumed"
unset TMUX_PANE  # a real pane id could collide with the private server's
cleanup() {
    t kill-server 2>/dev/null || true
    rm -rf "$test_root"
}
trap cleanup EXIT HUP INT TERM
tp="$repo_root/shell/tmux-persist"
t() { tmux -L "$TMUX_PERSIST_SOCKET" "$@"; }

fail() { echo "FAIL: $*" >&2; exit 1; }

mkdir -p "$TMUX_PERSIST_STATE" "$TMUX_PERSIST_CLAUDE_SESSIONS"

# session <pid> <procStart> <tmux> <id>
session() {
    jq -n --argjson p "$1" --arg s "$2" --arg t "$3" --arg i "$4" --arg c "$test_root" \
        '{pid: $p, procStart: $s, tmux: $t, cwd: $c, sessionId: $i}' \
        > "$TMUX_PERSIST_CLAUDE_SESSIONS/$1.json"
}
# busy <session> <id> [<flag>...]: start a fake Claude in <session> launched with
# <flag>s, record its session file, and leave its pid and pane in busy_pid and busy_pane.
busy() {
    t kill-session -t "=$1" 2>/dev/null || true
    t new-session -d -s "$1" -c "$test_root" "perl -e 'sleep 600' -- ${*:3}"
    busy=$(t display -p -t "=$1:" '#{pane_pid} #{pane_id}')
    busy_pid=${busy% *} busy_pane=${busy#* }
    busy_epoch=$(LC_ALL=C /bin/date -j -f '%a %b %d %T %Y' "$(LC_ALL=C /bin/ps -o lstart= -p "$busy_pid" | xargs)" +%s)
    session "$busy_pid" "$(LC_ALL=C /bin/date -u -r "$busy_epoch" '+%a %b %d %T %Y')" "$1:@9.$busy_pane" "$2"
}
# resumed <pid> <pane> <id>: wait until <pane> resumed <id>, telling it about the
# restart, and the old Claude <pid> is gone.
resumed() {
    tries=0
    until t capture-pane -p -J -t "$2" | grep -q "^resumed $3 .*重启"; do
        tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "resume $3 not run in restarted pane"
        sleep 0.1
    done
    ! kill -0 "$1" 2>/dev/null || fail "old Claude still running"
}
snap() { cat "$TMUX_PERSIST_STATE/snapshot"; }
row() { printf '%s\t%s\t%s\t%s' "$1" "$test_root" "$2" "${3:-}"; }

# No tmux server yet (as at boot): save leaves the snapshot alone.
printf 'gone-r2v\t/x\tid-gone\n' > "$TMUX_PERSIST_STATE/snapshot"
"$tp" save
[ "$(snap)" = "$(printf 'gone-r2v\t/x\tid-gone')" ] || fail "save without tmux changed snapshot: $(snap)"

# adapt-clf is persisted too, though it is not named *-r2v.
busy adapt-clf id-adapt
"$tp" save
[ "$(snap)" = "$(row adapt-clf id-adapt)" ] || fail "adapt-clf not saved: $(snap)"
t kill-session -t "=adapt-clf"

# Only persisted sessions are saved, under their current name after a rename; a
# closed session drops out and a reused pid is ignored.
busy keep-r2v id-keep; keep_pid=$busy_pid keep_pane=$busy_pane
busy other id-other
busy old id-renamed
t rename-session -t "=old" renamed-r2v
busy stale-r2v id-ignored
session "$$" "Thu Jan 01 00:00:00 1970" "stale-r2v:@9.$busy_pane" id-stale   # pid reused: wrong start
rm "$TMUX_PERSIST_CLAUDE_SESSIONS/$busy_pid.json"
"$tp" save
[ "$(snap)" = "$(row keep-r2v id-keep; echo; row renamed-r2v id-renamed)" ] || fail "snapshot: $(snap)"
"$tp" | grep -qxF "$(printf 'stale-r2v\t(no snapshot)')" || fail "status missing unsnapshotted session"

# An open session whose Claude has exited keeps its last known entry.
rm "$TMUX_PERSIST_CLAUDE_SESSIONS/$keep_pid.json"
"$tp" save
grep -q "id-keep" "$TMUX_PERSIST_STATE/snapshot" || fail "entry dropped when Claude was not running"

# A closed session is not brought back.
t kill-session -t "=renamed-r2v"
"$tp" save
[ "$(snap)" = "$(row keep-r2v id-keep)" ] || fail "closed session kept: $(snap)"

# After a reboot (no tmux server), restore recreates the snapshot sessions.
t kill-server
[ "$("$tp" restore)" = "restored keep-r2v" ] || fail "restore did not report keep-r2v"
t has-session -t "=keep-r2v" || fail "keep-r2v not recreated"
tries=0
until t capture-pane -p -t "=keep-r2v:" | grep -q "^resumed id-keep"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "resume command not run in pane"
    sleep 0.1
done
[ "$(t display -p -t "=keep-r2v:" '#{pane_current_path}')" = "$(cd "$test_root" && pwd -P)" ] \
    || fail "pane not in snapshot cwd"

# The effort a Claude was launched with is saved and restored with it.
t kill-session -t "=keep-r2v"
busy keep-r2v id-keep --effort high
"$tp" save
[ "$(snap)" = "$(row keep-r2v id-keep high)" ] || fail "effort not saved: $(snap)"
t kill-server
"$tp" restore > /dev/null
tries=0
until t capture-pane -p -t "=keep-r2v:" | grep -qxF "resumed id-keep --effort high"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "effort not restored: $(t capture-pane -p -t "=keep-r2v:")"
    sleep 0.1
done

# Running sessions are left alone.
[ -z "$("$tp" restore)" ] || fail "restore touched a running session"

# restart replaces the Claude in a running pane and resumes its conversation.
busy busy id-busy
[ "$("$tp" restart busy)" = "restarted busy ($busy_pane)" ] || fail "restart did not report busy"
resumed "$busy_pid" "$busy_pane" id-busy

# Run from inside the Claude's own pane, the restart is handed to the tmux server.
busy busy id-inside
[ -z "$(TMUX_PANE=$busy_pane "$tp" restart busy)" ] || fail "in-pane restart did not hand off"
resumed "$busy_pid" "$busy_pane" id-inside

# Several sessions restart together.
busy one id-one; one_pid=$busy_pid one_pane=$busy_pane
busy two id-two
[ "$("$tp" restart one two | sort)" = "$(printf 'restarted one (%s)\nrestarted two (%s)' "$one_pane" "$busy_pane" | sort)" ] \
    || fail "restart did not report both sessions"
resumed "$one_pid" "$one_pane" id-one
resumed "$busy_pid" "$busy_pane" id-two

# restart keeps the effort the old Claude was launched with, as --effort or --effort=.
busy busy id-high --effort high
"$tp" restart busy > /dev/null
resumed "$busy_pid" "$busy_pane" "id-high --effort high"
busy busy id-eq --effort=xhigh
"$tp" restart busy > /dev/null
resumed "$busy_pid" "$busy_pane" "id-eq --effort xhigh"

# restart --effort sets the level for the restarted sessions.
busy busy id-set --effort high
"$tp" restart --effort medium busy > /dev/null
resumed "$busy_pid" "$busy_pane" "id-set --effort medium"

# A session without a running Claude stops the whole restart.
busy busy id-untouched
! "$tp" restart busy missing 2>/dev/null || fail "restart succeeded without a running Claude"
kill -0 "$busy_pid" 2>/dev/null || fail "restart touched busy although missing has no Claude"

# stale lists each session whose Claude predates the installed version, once.
# version <pid> <v>: record the Claude Code version in <pid>'s session file.
version() {
    f="$TMUX_PERSIST_CLAUDE_SESSIONS/$1.json"
    jq --arg v "$2" '.version = $v' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
}
busy old-r2v id-old; version "$busy_pid" 2.0.1
t split-window -t "=old-r2v:" "sleep 600"
split=$(t display -p -t "=old-r2v:" '#{pane_pid} #{pane_id}')
session "${split% *}" "$(LC_ALL=C /bin/date -u -r "$(LC_ALL=C /bin/date -j -f '%a %b %d %T %Y' "$(LC_ALL=C /bin/ps -o lstart= -p "${split% *}" | xargs)" +%s)" '+%a %b %d %T %Y')" "old-r2v:@9.${split#* }" id-old2
version "${split% *}" 2.0.1
busy new-r2v id-new; version "$busy_pid" 2.0.2
[ "$(TMUX_PERSIST_VERSION='2.0.2 (Claude Code)' "$tp" stale)" = "old-r2v" ] || fail "stale: $(TMUX_PERSIST_VERSION=2.0.2 "$tp" stale)"

echo "ok"
