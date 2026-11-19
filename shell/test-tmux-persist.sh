#!/bin/sh
# Offline checks for shell/tmux-persist against fake Claude session files and a
# private tmux server (-L), so real sessions and Claude are never touched.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/tmux-persist-test.XXXXXX")
export TMUX_PERSIST_STATE="$test_root/state" TMUX_PERSIST_CLAUDE_SESSIONS="$test_root/sessions"
export TMUX_PERSIST_CLAUDE_PROJECTS="$test_root/projects"
export TMUX_PERSIST_SOCKET="tmux-persist-test-$$" TMUX_PERSIST_LAUNCH="echo resumed"
export TMUX_PERSIST_AGY_LAUNCH="echo agy-resumed" TMUX_PERSIST_AGY_PRESENCE="$test_root/presence"
# The fake Claudes that show no launch dialog need not be waited on for long.
export TMUX_PERSIST_DIALOG_WAIT=20
# No peer channel unless a check sets one (see the peer checks below).
export TMUX_PERSIST_PEER_MCP=""
# No per-session model config unless a check writes one.
export AGENT_MODELS="$test_root/agent-models.conf"
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
# resumed <pid> <pane> <id> [<flags>]: wait until <pane> resumed <id>, telling it
# about the restart right after the id (multi-value flags such as --mcp-config
# would take it as one of their values), then <flags>, and the old Claude <pid> is gone.
resumed() {
    tries=0
    until t capture-pane -p -J -t "$2" | grep -q "^resumed $3 这个会话.*重启.*${4:+ $4}\$"; do
        tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "resume $3 not run in restarted pane"
        sleep 0.1
    done
    ! kill -0 "$1" 2>/dev/null || fail "old Claude still running"
}
snap() { cat "$TMUX_PERSIST_STATE/snapshot"; }
row() { printf '%s\t%s\t%s\t%s\t%s' "$1" "$test_root" "$2" "${3:-}" "${4:-}"; }

# No tmux server yet (as at boot): save leaves the snapshot alone.
printf 'gone-r2v\t/x\tid-gone\n' > "$TMUX_PERSIST_STATE/snapshot"
"$tp" save
[ "$(snap)" = "$(printf 'gone-r2v\t/x\tid-gone')" ] || fail "save without tmux changed snapshot: $(snap)"

# adapt-clf is persisted too, though it is not named *-r2v.
busy adapt-clf id-adapt
"$tp" save
[ "$(snap)" = "$(row adapt-clf id-adapt)" ] || fail "adapt-clf not saved: $(snap)"
t kill-session -t "=adapt-clf"

# So is thesis.
busy thesis id-thesis
"$tp" save
[ "$(snap)" = "$(row thesis id-thesis)" ] || fail "thesis not saved: $(snap)"
t kill-session -t "=thesis"

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

# Channel launch flags (--mcp-config, --dangerously-load-development-channels,
# --channels) are saved and restored with it; other flags are not.
t kill-session -t "=keep-r2v"
busy keep-r2v id-ch --effort high --mcp-config /x/mcp.json --dangerously-load-development-channels server:avatar --channels=plugin:p@m --verbose
"$tp" save
[ "$(snap)" = "$(row keep-r2v id-ch high '--mcp-config /x/mcp.json --dangerously-load-development-channels server:avatar --channels plugin:p@m')" ] \
    || fail "channel flags not saved: $(snap)"
t kill-server
"$tp" restore > /dev/null
tries=0
until t capture-pane -p -J -t "=keep-r2v:" | grep -qxF "resumed id-ch --effort high --mcp-config /x/mcp.json --dangerously-load-development-channels server:avatar --channels plugin:p@m"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "channel flags not restored: $(t capture-pane -p -J -t "=keep-r2v:")"
    sleep 0.1
done

# Without an effort, the flags stay in their own column (an empty column must not
# collapse), and a flag keeps all of its values.
t kill-session -t "=keep-r2v"
busy keep-r2v id-noeff --channels plugin:a@m plugin:b@m --verbose
"$tp" save
[ "$(snap)" = "$(row keep-r2v id-noeff '' '--channels plugin:a@m plugin:b@m')" ] || fail "flags without effort not saved: $(snap)"
t kill-server
"$tp" restore > /dev/null
tries=0
until t capture-pane -p -J -t "=keep-r2v:" | grep -qxF "resumed id-noeff --channels plugin:a@m plugin:b@m"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "flags without effort not restored: $(t capture-pane -p -J -t "=keep-r2v:")"
    sleep 0.1
done

# A snapshot written before the flags column still restores.
t kill-server
printf 'old-r2v\t%s\tid-old4\thigh\n' "$test_root" > "$TMUX_PERSIST_STATE/snapshot"
"$tp" restore > /dev/null
tries=0
until t capture-pane -p -J -t "=old-r2v:" | grep -qxF "resumed id-old4 --effort high"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "old snapshot not restored: $(t capture-pane -p -J -t "=old-r2v:")"
    sleep 0.1
done
t kill-session -t "=old-r2v"

# The model and effort a session runs now (from its transcript) outrank the ones it
# was launched with, so /model and /effort survive a restore; a replayed
# api-request-blob line must not be mistaken for the last request.
mkdir -p "$TMUX_PERSIST_CLAUDE_PROJECTS/proj"
{
    printf '{"type":"api-request","querySource":"repl_main_thread","params":{"model":"claude-fable-5-2","output_config":{"effort":"high"}}}\n'
    printf '{"type":"api-request-blob","querySource":"repl_main_thread","params":{"model":"claude-opus-5-5","output_config":{"effort":"low"}}}\n'
} > "$TMUX_PERSIST_CLAUDE_PROJECTS/proj/id-live.jsonl"
busy keep-r2v id-live --model claude-opus-5-5 --effort medium
"$tp" save
[ "$(snap)" = "$(printf '%s\tclaude-fable-5-2' "$(row keep-r2v id-live high)")" ] \
    || fail "live model/effort not saved: $(snap)"
t kill-server
TMUX_PERSIST_LAUNCH="echo resumed --model claude-opus-5-5" "$tp" restore > /dev/null
tries=0
until t capture-pane -p -J -t "=keep-r2v:" | grep -qxF "resumed --model claude-fable-5-2 id-live --effort high"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "live model not restored: $(t capture-pane -p -J -t "=keep-r2v:")"
    sleep 0.1
done
rm -f "$TMUX_PERSIST_CLAUDE_PROJECTS/proj/id-live.jsonl"
t kill-session -t "=keep-r2v" 2>/dev/null || true

# A session a refusal moved to the fallback keeps the launched model in the snapshot:
# a relaunch is one way out of the fallback, so it must not be pinned there.
printf '{"type":"api-request","querySource":"repl_main_thread","params":{"model":"claude-opus-5","output_config":{"effort":"high"}}}\n' \
    > "$TMUX_PERSIST_CLAUDE_PROJECTS/proj/id-fb.jsonl"
busy keep-r2v id-fb --model claude-opus-5-5 --effort high
"$tp" save
[ "$(snap)" = "$(printf '%s\tclaude-opus-5-5' "$(row keep-r2v id-fb high)")" ] \
    || fail "fallback model pinned into snapshot: $(snap)"
rm -f "$TMUX_PERSIST_CLAUDE_PROJECTS/proj/id-fb.jsonl"
t kill-session -t "=keep-r2v" 2>/dev/null || true

# agent-models.conf outranks what a session runs now on restore and restart, and
# restart --effort outranks its level; "-" leaves the level to the session.
# wait_line <target> <regex>: wait until a line of pane <target> matches <regex>
# (a restart puts its message, which these fake Claudes are owed, after the id).
wait_line() {
    tries=0
    until t capture-pane -p -J -t "$1" | grep -qE -- "$2"; do
        tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "expected '$2' in $1: $(t capture-pane -p -J -t "$1")"
        sleep 0.1
    done
}
printf '{"type":"api-request","querySource":"repl_main_thread","params":{"model":"claude-fable-5-2","output_config":{"effort":"high"}}}\n' \
    > "$TMUX_PERSIST_CLAUDE_PROJECTS/proj/id-conf.jsonl"
printf '# session model effort\nkeep-r2v  claude-opus-5-5  xhigh\nother-r2v claude-fable-5-2 -\n' > "$AGENT_MODELS"
busy keep-r2v id-conf --model claude-fable-5-2 --effort high
"$tp" save
t kill-server
TMUX_PERSIST_LAUNCH="echo resumed --model claude-opus-5" "$tp" restore > /dev/null
wait_line "=keep-r2v:" "^resumed --model claude-opus-5-5 id-conf --effort xhigh$"
busy keep-r2v id-conf --model claude-fable-5-2 --effort high
TMUX_PERSIST_LAUNCH="echo resumed --model claude-opus-5" "$tp" restart --effort low keep-r2v > /dev/null
wait_line "=keep-r2v:" "^resumed --model claude-opus-5-5 id-conf .* --effort low$"
busy other-r2v id-conf --model claude-opus-5-5 --effort medium
TMUX_PERSIST_LAUNCH="echo resumed --model claude-opus-5" "$tp" restart other-r2v > /dev/null
wait_line "=other-r2v:" "^resumed --model claude-fable-5-2 id-conf .* --effort high$"
rm -f "$AGENT_MODELS" "$TMUX_PERSIST_CLAUDE_PROJECTS/proj/id-conf.jsonl"
t kill-session -t "=keep-r2v" 2>/dev/null || true
t kill-session -t "=other-r2v" 2>/dev/null || true

busy keep-r2v id-keep --effort high
"$tp" save

# Running sessions are left alone.
[ -z "$("$tp" restore)" ] || fail "restore touched a running session"

# restart replaces the Claude in a running pane and resumes its conversation.
busy busy id-busy
[ "$("$tp" restart busy)" = "restarted busy ($busy_pane)" ] || fail "restart did not report busy"
resumed "$busy_pid" "$busy_pane" id-busy

# A Claude that reports itself idle and has no subagent left unfinished since it started
# resumes without the restart message. Its session crons and wakeups need none: Claude
# re-arms them itself on --resume. startedAt is set two hours back, so "since" has room.
start=$(($(date +%s) - 7200))
log_dir="$TMUX_PERSIST_CLAUDE_PROJECTS/-proj"
# idle <session> <id> [<status>]: a fake Claude like busy's, reporting <status> (idle).
idle() {
    busy "$1" "$2"
    f="$TMUX_PERSIST_CLAUDE_SESSIONS/$busy_pid.json"
    jq --arg s "${3:-idle}" --argjson t "$((start * 1000))" '.status = $s | .startedAt = $t' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
}
# agent <id> <name> <meta> [<touch time>]: a subagent of <id>, its transcript last written then.
agent() {
    mkdir -p "$log_dir/$1/subagents"
    printf '%s' "$3" > "$log_dir/$1/subagents/agent-$2.meta.json"
    : > "$log_dir/$1/subagents/agent-$2.jsonl"
    [ -z "${4:-}" ] || touch -t "$4" "$log_dir/$1/subagents/agent-$2.meta.json" "$log_dir/$1/subagents/agent-$2.jsonl"
}
# plain <pid> <pane> <id>: like resumed, but without the restart message.
plain() {
    tries=0
    until t capture-pane -p -J -t "$2" | grep -qxF "resumed $3"; do
        tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "$3 not resumed without the message: $(t capture-pane -p -J -t "$2")"
        sleep 0.1
    done
    ! kill -0 "$1" 2>/dev/null || fail "old Claude still running"
}
restarts() { "$tp" restart busy > /dev/null; }

# Nothing at all, or only a subagent an earlier process left: no message.
idle busy id-quiet; restarts; plain "$busy_pid" "$busy_pane" id-quiet
agent id-old a1 '{"agentType": "general-purpose"}' "$(/bin/date -r "$((start - 600))" '+%Y%m%d%H%M.%S')"
idle busy id-old; restarts; plain "$busy_pid" "$busy_pane" id-old
# A turn, a background shell or a permission prompt in progress (or no status at all,
# as in the checks above): the message.
idle busy id-turn busy; restarts; resumed "$busy_pid" "$busy_pane" id-turn
idle busy id-shell shell; restarts; resumed "$busy_pid" "$busy_pane" id-shell
idle busy id-wait waiting; restarts; resumed "$busy_pid" "$busy_pane" id-wait
# A subagent written to since the start without "finished":true keeps the message.
agent id-sub s1 '{"agentType": "general-purpose"}'
idle busy id-sub; restarts; resumed "$busy_pid" "$busy_pane" id-sub
agent id-done s2 '{"agentType": "general-purpose", "finished": true}'
idle busy id-done; restarts; plain "$busy_pid" "$busy_pane" id-done

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
resumed "$busy_pid" "$busy_pane" id-high "--effort high"
busy busy id-eq --effort=xhigh
"$tp" restart busy > /dev/null
resumed "$busy_pid" "$busy_pane" id-eq "--effort xhigh"

# restart keeps the channel launch flags too.
busy busy id-chr --mcp-config /x/mcp.json --dangerously-load-development-channels server:avatar
"$tp" restart busy > /dev/null
resumed "$busy_pid" "$busy_pane" id-chr "--mcp-config /x/mcp.json --dangerously-load-development-channels server:avatar"

# With a peer channel set, restart and restore add it to every session's flags: its config
# joins an existing --mcp-config and server:peer an existing channel list, else both are
# added; a session that has them already keeps one copy.
peer=$test_root/peer-mcp.json; : > $peer
busy busy id-pr --mcp-config /x/mcp.json --dangerously-load-development-channels server:avatar
TMUX_PERSIST_PEER_MCP=$peer "$tp" restart busy > /dev/null
resumed "$busy_pid" "$busy_pane" id-pr "--mcp-config /x/mcp.json $peer --dangerously-load-development-channels server:avatar server:peer"
busy busy id-pn
TMUX_PERSIST_PEER_MCP=$peer "$tp" restart busy > /dev/null
resumed "$busy_pid" "$busy_pane" id-pn "--mcp-config $peer --dangerously-load-development-channels server:peer"
busy busy id-pd --mcp-config $peer --dangerously-load-development-channels server:peer
TMUX_PERSIST_PEER_MCP=$peer "$tp" restart busy > /dev/null
resumed "$busy_pid" "$busy_pane" id-pd "--mcp-config $peer --dangerously-load-development-channels server:peer"
t kill-session -t "=peer-r2v" 2>/dev/null || true
printf 'peer-r2v\t%s\tid-prs\t\t\n' "$test_root" > "$TMUX_PERSIST_STATE/snapshot"
TMUX_PERSIST_PEER_MCP=$peer TMUX_PERSIST_DIALOG_WAIT=1 "$tp" restore > /dev/null
tries=0
until t capture-pane -p -J -t "=peer-r2v:" | grep -qxF "resumed id-prs --mcp-config $peer --dangerously-load-development-channels server:peer"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "peer channel not added on restore: $(t capture-pane -p -J -t "=peer-r2v:")"
    sleep 0.1
done
t kill-session -t "=peer-r2v"

# A development channel's launch dialog is accepted on restart and restore: a fake
# Claude shows it and resumes only after Enter.
dialog="$test_root/dialog"
cat > "$dialog" <<'SH'
#!/bin/sh
printf '  WARNING: Loading development channels\n  --dangerously-load-development-channels is for local channel development only.\n  Channels: server:avatar\n  \342\235\257 1. I am using this for local development\n    2. Exit\n  Enter to confirm \302\267 Esc to cancel\n'
read -r _
echo "accepted $*"
SH
chmod +x "$dialog"
# A resumed conversation quoting that dialog has its input box below it: no Enter.
quoted="$test_root/quoted"
cat > "$quoted" <<'SH'
#!/bin/sh
printf '  WARNING: Loading development channels\n  --dangerously-load-development-channels is for local channel development only.\n  Channels: server:avatar\n  \342\235\257 1. I am using this for local development\n    2. Exit\n  Enter to confirm \302\267 Esc to cancel\n\n\342\235\257 \n'
read -r _
echo "wrongly accepted"
SH
chmod +x "$quoted"
busy busy id-quoted --dangerously-load-development-channels server:avatar
TMUX_PERSIST_LAUNCH="$quoted" "$tp" restart busy > /dev/null 2>&1
! t capture-pane -p -J -t "$busy_pane" | grep -q "wrongly accepted" || fail "Enter pressed on a quoted dialog"
busy busy id-dlg --mcp-config /x/mcp.json --dangerously-load-development-channels server:avatar
TMUX_PERSIST_LAUNCH="$dialog" "$tp" restart busy > /dev/null
tries=0
until t capture-pane -p -J -t "$busy_pane" | grep -q "^accepted id-dlg 这个会话.*重启.* --mcp-config /x/mcp.json --dangerously-load-development-channels server:avatar\$"; do
    tries=$((tries + 1)); [ "$tries" -lt 100 ] || fail "dialog not accepted on restart: $(t capture-pane -p -J -t "$busy_pane")"
    sleep 0.1
done
t kill-server
printf 'dlg-r2v\t%s\tid-dlg2\t\t--dangerously-load-development-channels server:avatar\n' "$test_root" > "$TMUX_PERSIST_STATE/snapshot"
TMUX_PERSIST_LAUNCH="$dialog" "$tp" restore > /dev/null
tries=0
until t capture-pane -p -J -t "=dlg-r2v:" | grep -qxF "accepted id-dlg2 --dangerously-load-development-channels server:avatar"; do
    tries=$((tries + 1)); [ "$tries" -lt 100 ] || fail "dialog not accepted on restore: $(t capture-pane -p -J -t "=dlg-r2v:")"
    sleep 0.1
done
t kill-server
rm "$TMUX_PERSIST_STATE/snapshot"

# restart --effort sets the level for the restarted sessions.
busy busy id-set --effort high
"$tp" restart --effort medium busy > /dev/null
resumed "$busy_pid" "$busy_pane" id-set "--effort medium"

# restart --all restarts every session running a Claude, and only those.
t kill-server
busy one id-all1; one_pid=$busy_pid one_pane=$busy_pane
busy two id-all2
t new-session -d -s plain "sleep 600"
[ "$("$tp" restart --effort low --all | sort)" = "$(printf 'restarted one (%s)\nrestarted two (%s)' "$one_pane" "$busy_pane" | sort)" ] \
    || fail "restart --all did not report exactly the Claude sessions"
resumed "$one_pid" "$one_pane" id-all1 "--effort low"
resumed "$busy_pid" "$busy_pane" id-all2 "--effort low"
! "$tp" restart --all one 2>/dev/null || fail "restart --all accepted session names"

# A session without a running Claude stops the whole restart.
busy busy id-untouched
! "$tp" restart busy missing 2>/dev/null || fail "restart succeeded without a running Claude"
kill -0 "$busy_pid" 2>/dev/null || fail "restart touched busy although missing has no Claude"

# A Claude that a session's tool started (agent-team, a nested `claude -p`) inherits the pane's
# TMUX_PANE and so records the same pane; it is not the pane's Claude, so restart and save
# leave it alone instead of "restarting" the pane a second time with the child's id.
busy busy id-main
perl -e 'sleep 600' & child=$!
child_epoch=$(LC_ALL=C /bin/date -j -f '%a %b %d %T %Y' "$(LC_ALL=C /bin/ps -o lstart= -p "$child" | xargs)" +%s)
session "$child" "$(LC_ALL=C /bin/date -u -r "$child_epoch" '+%a %b %d %T %Y')" "busy:@9.$busy_pane" id-child
out=$("$tp" restart busy)
[ "$out" = "restarted busy ($busy_pane)" ] || fail "restart counted a tool's child Claude as the pane's: $out"
resumed "$busy_pid" "$busy_pane" id-main
kill -0 "$child" 2>/dev/null || fail "restart killed a tool's child Claude"
kill "$child"

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

# agy: a live agy is found by the presence lock it holds open, saved with its launch model and
# level, and restored and restarted through AGY_LAUNCH on the model agent-models.conf sets.
conv=0983f4bc-882e-40fc-aec2-1af2030a8130
mkdir -p "$TMUX_PERSIST_AGY_PRESENCE"; : > "$TMUX_PERSIST_AGY_PRESENCE/$conv.lock"
t new-session -d -s train-agy-r2v -c "$test_root" \
    "exec -a agy perl -e 'open my \$f, \"<\", shift; sleep 600' $TMUX_PERSIST_AGY_PRESENCE/$conv.lock --model gemini-4-neon --effort low"
agy=$(t display -p -t "=train-agy-r2v:" '#{pane_pid} #{pane_id}'); agy_pid=${agy% *} agy_pane=${agy#* }
tries=0
until "$tp" save && grep -q '^train-agy-r2v' "$TMUX_PERSIST_STATE/snapshot"; do
    tries=$((tries + 1)); [ "$tries" -lt 30 ] || fail "save missed the agy session"; sleep 0.1
done
[ "$(grep '^train-agy-r2v' "$TMUX_PERSIST_STATE/snapshot")" = "$(printf 'train-agy-r2v\t%s\t%s\tlow\t\tgemini-4-neon\tagy' "$(cd "$test_root" && pwd -P)" "$conv")" ] \
    || fail "agy snapshot row: $(grep '^train-agy-r2v' "$TMUX_PERSIST_STATE/snapshot" | cat -t)"
printf 'train-agy-r2v gemini-4-carbon high\n' > "$AGENT_MODELS"
[ "$("$tp" restart train-agy-r2v)" = "restarted train-agy-r2v ($agy_pane)" ] || fail "agy restart"
tries=0
until t capture-pane -p -J -t "$agy_pane" | grep -q "^agy-resumed $conv --model gemini-4-carbon --effort high -i 这个会话刚被重启.*manage_task list.*继续当前任务。$"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "agy not resumed: $(t capture-pane -p -J -t "$agy_pane")"; sleep 0.1
done
! kill -0 "$agy_pid" 2>/dev/null || fail "old agy still running"
t kill-session -t "=train-agy-r2v"
"$tp" restore >/dev/null
tries=0
until t capture-pane -p -J -t "=train-agy-r2v:" 2>/dev/null | grep -q "^agy-resumed $conv --model gemini-4-carbon --effort high -i 这个会话刚被重启.*manage_task list.*继续当前任务。$"; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "agy not restored"; sleep 0.1
done
# A Claude model set for an agy session (the file not yet updated after a switch) is ignored and
# noted; its level still applies.
t kill-session -t "=train-agy-r2v"
printf 'train-agy-r2v claude-opus-5-5 medium\n' > "$AGENT_MODELS"
"$tp" restore >/dev/null 2>&1
tries=0
until t capture-pane -p -J -t "=train-agy-r2v:" 2>/dev/null | grep -q "^agy-resumed $conv --model gemini-4-neon --effort medium -i "; do
    tries=$((tries + 1)); [ "$tries" -lt 50 ] || fail "agy given a Claude model: $(t capture-pane -p -J -t "=train-agy-r2v:" 2>&1)"; sleep 0.1
done
grep -q 'train-agy-r2v runs agy, so its model claude-opus-5-5 is ignored' "$TMUX_PERSIST_STATE/dialog.log" || fail "mismatch not noted"
t kill-session -t "=train-agy-r2v"
: > "$AGENT_MODELS"

echo "ok"
