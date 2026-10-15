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
#   bash opus-repin.sh session-start   # SessionStart hook, matcher "compact"
#   bash opus-repin.sh pre-switch      # PreModelSwitch hook
set -u

TARGET=claude-opus-5-5
COMMAND="/model $TARGET"
TTL=180 # seconds an approval stays valid
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/opus-repin"
input=$(cat)
sid=$(jq -r '.session_id // empty' <<<"$input")
[[ -n "$sid" ]] || exit 0
mkdir -p "$STATE"
log() { printf '%s %s %s\n' "$(date +%FT%T%z)" "${sid:0:8}" "$*" >> "$STATE/log"; }

# The bottom input line of the pane, without the prompt marker.
input_line() {
    tmux capture-pane -p -t "$1" 2>/dev/null | grep '^❯' | tail -1 | sed $'s/\xc2\xa0/ /g' | sed 's/^❯ *//; s/ *$//'
}

# The pane still runs Claude Code (the binary shows up as its version number).
pane_is_claude() {
    [[ "$(tmux display -p -t "$1" '#{pane_current_command}' 2>/dev/null)" =~ ^(claude|[0-9]+\.[0-9]+\.[0-9]+)$ ]]
}

fresh() { [[ -f "$1" && $(($(date +%s) - $(/usr/bin/stat -f %m "$1"))) -lt $TTL ]]; }

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
    fallback=$(grep -a -n '"subtype":"model_refusal_fallback"' "$transcript" | tail -1)
    [[ -n "$fallback" ]] || exit 0
    line=${fallback%%:*}
    fallback=${fallback#*:}
    [[ "$(jq -r '.originalModel // empty' <<<"$fallback")" == "$TARGET" ]] || exit 0
    model=$(jq -r '.model // empty' <<<"$input")
    [[ "$model" == "$(jq -r '.fallbackModel // empty' <<<"$fallback")" ]] || exit 0
    # Only undo the fallback itself: a /model run after it is a choice to keep.
    tail -n +"$((line + 1))" "$transcript" | grep -aq '<command-name>/model</command-name>' && exit 0
    fresh "$STATE/$sid" && exit 0 # another attempt is in flight
    touch "$STATE/$sid"
    log "compacted on $model after a $TARGET refusal; typing /model in $pane"
    (
        # A queued /model may only show up as the next request's model attachment.
        switched() { grep -a -c -e 'Set model to `Opus 5.5`' -e "\"modelId\":\"$TARGET\"" "$transcript"; }
        for _ in $(seq 120); do
            sleep 1
            pane_is_claude "$pane" || break
            [[ -z "$(input_line "$pane")" || "$(input_line "$pane")" == Try\ \"* ]] || continue
            before=$(switched)
            tmux send-keys -t "$pane" -l "$COMMAND"
            sleep 0.5
            if [[ "$(input_line "$pane")" != "$COMMAND" ]]; then
                log "input changed while typing; not submitting"
                exit 0
            fi
            tmux send-keys -t "$pane" Enter
            for _ in $(seq 240); do
                sleep 0.5
                [[ $(switched) -gt $before ]] && { log "switched to $TARGET"; exit 0; }
            done
            log "switch to $TARGET not confirmed"
            exit 0
        done
        rm -f "$STATE/$sid"
        log "pane $pane not ready or not Claude Code; gave up"
    ) </dev/null >/dev/null 2>&1 &
    ;;
esac
exit 0
