#!/usr/bin/env bash
# Switch a Claude Code session back to Opus 5.5 after a compaction when its
# current model came from a safeguards refusal fallback.
#
# A refusal fallback swaps the session to the fallback model for good. This
# retries 5.5 once per compaction; it is a recovery attempt, not a sign that
# the context is safe (the first request after a compaction is often refused
# again). No hook output can change the model, so the SessionStart(compact)
# hook types `/model` into the session's tmux pane, and the PreModelSwitch hook
# approves that one switch so no cache-miss confirm blocks an unattended session.
#
#
# While on the fallback, the session keeps the effort level the refused request
# ran at, and the fallback thinks less per level, so the PostModelSwitch hook
# types `/effort $FALLBACK_EFFORT` after an automatic switch to the fallback,
# and `/effort <level saved for 5.5>` after a switch from it back to 5.5,
# accepting the cache-miss dialog /effort shows while the cache is warm. A
# session resumed on the fallback loses that level, so the SessionStart(resume)
# hook types it again. The fallback inherits the level of the refused request,
# which `/model` has usually already set to 5.5's saved level; changing the
# level rewrites the whole cached context, so the hook skips it only when that
# request already ran at the fallback level.
#
# Sessions named in $STATE/pinned (one agent name per line) stay on the
# fallback: for them 5.5 refuses almost every first request after a compaction,
# so retrying only rewrites the cache.
#
#   bash opus-repin.sh session-start   # SessionStart hook, matcher "compact"
#   bash opus-repin.sh session-resume  # SessionStart hook, matcher "resume"
#   bash opus-repin.sh pre-switch      # PreModelSwitch hook
#   bash opus-repin.sh post-switch     # PostModelSwitch hook
set -u

TARGET=claude-opus-5-5
COMMAND="/model $TARGET"
FALLBACK=claude-opus-5
FALLBACK_EFFORT=xhigh
TTL=180 # seconds an approval stays valid
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/opus-repin"
input=$(cat)
sid=$(jq -r '.session_id // empty' <<<"$input")
[[ -n "$sid" ]] || exit 0
mkdir -p "$STATE"
log() { printf '%s %s %s\n' "$(date +%FT%T%z)" "${sid:0:8}" "$*" >> "$STATE/log"; }

# The bottom input line of the pane, without the prompt marker. Fails when no
# prompt shows, as while a dialog covers it.
input_line() {
    local line
    line=$(tmux capture-pane -p -t "$1" 2>/dev/null | grep '^❯' | tail -1)
    [[ -n "$line" ]] || return 1
    sed $'s/\xc2\xa0/ /g' <<<"$line" | sed 's/^❯ *//; s/ *$//'
}

# The level an open "Change effort level?" dialog offers to switch to, if any.
effort_dialog() {
    tmux capture-pane -p -t "$1" 2>/dev/null | sed $'s/\xc2\xa0/ /g' | sed -n 's/.*❯ 1\. Yes, switch to \([a-z]*\) *$/\1/p' | tail -1
}

# While the cache is warm, /effort asks before re-reading the history. Accept
# the dialog for level $2 (its default option); decline one for another level,
# which a superseded /effort left behind.
answer_effort_dialog() {
    local level
    level=$(effort_dialog "$1")
    if [[ "$level" == "$2" ]]; then
        tmux send-keys -t "$1" Enter
        log "accepted the cache-miss dialog for /effort $level"
    elif [[ -n "$level" ]]; then
        tmux send-keys -t "$1" Escape
        log "declined the stale dialog for /effort $level"
    fi
}

# The pane still runs Claude Code (the binary shows up as its version number).
pane_is_claude() {
    [[ "$(tmux display -p -t "$1" '#{pane_current_command}' 2>/dev/null)" =~ ^(claude|[0-9]+\.[0-9]+\.[0-9]+)$ ]]
}

fresh() { [[ -f "$1" && $(($(date +%s) - $(/usr/bin/stat -f %m "$1"))) -lt $TTL ]]; }

# Transcript records, without the api-request-blob lines that replay the whole
# conversation history (and so every earlier /model or "Set model to" in it).
records() { grep -a -v '^{"type":"api-request-blob"' "$1"; }

# The main-thread request records of transcript $1.
main_requests() { grep -a '^{"type":"api-request",' "$1" | grep -a '"querySource":"repl_main_thread"'; }

# The effort level of the latest main-thread request in transcript $1.
last_effort() { main_requests "$1" | tail -1 | jq -r '.params.output_config.effort // empty'; }

# Type $2 into pane $1 once its input line is empty, submit it, and wait until
# the caller's confirmed() count rises; stop once the caller's wanted() fails.
# Returns 1 when the pane never got ready.
type_when_idle() {
    local pane=$1 cmd=$2 before line
    for _ in $(seq 120); do
        sleep 1
        pane_is_claude "$pane" || break
        wanted || { log "superseded: $cmd"; return 0; }
        [[ "$cmd" == /effort\ * ]] && answer_effort_dialog "$pane" "${cmd#/effort }"
        line=$(input_line "$pane") || continue
        [[ -z "$line" || "$line" == Try\ \"* ]] || continue
        before=$(confirmed)
        tmux send-keys -t "$pane" -l "$cmd"
        sleep 0.5
        if [[ "$(input_line "$pane")" != "$cmd" ]]; then
            log "input changed while typing; not submitting"
            return 0
        fi
        tmux send-keys -t "$pane" Enter
        for _ in $(seq 240); do
            sleep 0.5
            [[ $(confirmed) -gt $before ]] && { log "confirmed: $cmd"; return 0; }
            wanted || { log "superseded: $cmd"; return 0; }
            [[ "$cmd" == /effort\ * ]] && answer_effort_dialog "$pane" "${cmd#/effort }"
        done
        log "not confirmed: $cmd"
        return 0
    done
    log "pane $pane not ready or not Claude Code; gave up"
    return 1
}

# Type `/effort $1` into the session's pane in the background. A refusal right
# after the switch back starts a second /effort; only the latest typer keeps
# going, so the last level submitted is the latest one asked for.
type_effort() {
    local effort=$1 pane=${TMUX_PANE:-} transcript token
    [[ -n "$pane" ]] || return 0
    transcript=$(jq -r '.transcript_path // empty' <<<"$input")
    [[ -f "$transcript" ]] || return 0
    token="$(date +%s).$$"
    echo "$token" > "$STATE/$sid.effort"
    (
        # Accepting the cache-miss dialog prints no "Set effort level"; the next
        # request at that level is the only record of it.
        confirmed() {
            echo $(($(records "$transcript" | grep -a -c "Set effort level to $effort") +
                $(main_requests "$transcript" | grep -a -c "\"effort\":\"$effort\"")))
        }
        wanted() { [[ "$(cat "$STATE/$sid.effort" 2>/dev/null)" == "$token" ]]; }
        type_when_idle "$pane" "/effort $effort"
        wanted && rm -f "$STATE/$sid.effort"
    ) </dev/null >/dev/null 2>&1 &
}

case "${1:-}" in
pre-switch)
    fresh "$STATE/$sid" || exit 0
    [[ "$(jq -r '.to_model // empty' <<<"$input")" == "$TARGET" ]] || exit 0
    rm -f "$STATE/$sid"
    log "approve switch to $TARGET"
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreModelSwitch","permissionDecision":"allow"}}'
    ;;
session-start)
    pane=${TMUX_PANE:-}
    [[ -n "$pane" ]] || exit 0
    transcript=$(jq -r '.transcript_path // empty' <<<"$input")
    [[ -f "$transcript" ]] || exit 0
    fallback=$(records "$transcript" | grep -a -n '"subtype":"model_refusal_fallback"' | tail -1)
    [[ -n "$fallback" ]] || exit 0
    line=${fallback%%:*}
    fallback=${fallback#*:}
    [[ "$(jq -r '.originalModel // empty' <<<"$fallback")" == "$TARGET" ]] || exit 0
    model=$(jq -r '.model // empty' <<<"$input")
    [[ "$model" == "$(jq -r '.fallbackModel // empty' <<<"$fallback")" ]] || exit 0
    # Only undo the fallback itself: a /model run after it is a choice to keep.
    records "$transcript" | tail -n +"$((line + 1))" | grep -aq '<command-name>/model</command-name>' && exit 0
    name=$(grep -a '^{"type":"agent-name"' "$transcript" | tail -1 | jq -r '.agentName // empty')
    if [[ -n "$name" ]] && grep -qxF "$name" "$STATE/pinned" 2>/dev/null; then
        log "compacted on $model; $name is pinned there"
        exit 0
    fi
    fresh "$STATE/$sid" && exit 0 # another attempt is in flight
    touch "$STATE/$sid"
    log "compacted on $model after a $TARGET refusal; typing /model in $pane"
    (
        # A queued /model may only show up as the next request's model attachment,
        # or, when that first request is refused at once, as the refusal record.
        confirmed() { records "$transcript" | grep -a -c -e 'Set model to `Opus 5.5`' -e "\"modelId\":\"$TARGET\"" -e "\"originalModel\":\"$TARGET\""; }
        wanted() { :; }
        type_when_idle "$pane" "$COMMAND" || rm -f "$STATE/$sid"
    ) </dev/null >/dev/null 2>&1 &
    ;;
post-switch)
    # A level set with /effort outlives a model switch, so set it both ways:
    # the fallback level after the automatic fallback, and the level saved for
    # 5.5 when a switch from the fallback returns to it.
    source=$(jq -r '.source // empty' <<<"$input")
    from=$(jq -r '.from_model // empty' <<<"$input")
    to=$(jq -r '.to_model // empty' <<<"$input")
    from=${from%\[1m\]} to=${to%\[1m\]}
    if [[ "$source" == auto && "$to" == "$FALLBACK" ]]; then
        # The refused request may already have run at the fallback level (when
        # /model kept it); then only cancel an /effort the switch back queued.
        transcript=$(jq -r '.transcript_path // empty' <<<"$input")
        if [[ -f "$transcript" && "$(last_effort "$transcript")" == "$FALLBACK_EFFORT" ]]; then
            rm -f "$STATE/$sid.effort"
            log "switched $from -> $to ($source) at $FALLBACK_EFFORT already; keeping it"
            exit 0
        fi
        effort=$FALLBACK_EFFORT
    elif [[ "$from" == "$FALLBACK" && "$to" == "$TARGET" ]]; then
        effort=$(jq -r --arg m "$TARGET" '.modelSettings[$m].effortLevel // "medium"' "$HOME/.claude/settings.json")
    else
        exit 0
    fi
    log "switched $from -> $to ($source); typing /effort $effort"
    type_effort "$effort"
    ;;
session-resume)
    # A resumed session on the fallback starts at the level settings give it
    # without the one set with /effort before the restart, so set it again.
    model=$(jq -r '.model // empty' <<<"$input")
    if [[ "${model%\[1m\]}" != "$FALLBACK" ]]; then
        log "resumed on ${model:-an unreported model}; leaving effort alone"
        exit 0
    fi
    log "resumed on $model; typing /effort $FALLBACK_EFFORT"
    type_effort "$FALLBACK_EFFORT"
    ;;
esac
exit 0
