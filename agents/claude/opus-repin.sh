#!/usr/bin/env bash
# Switch a Claude Code session back to Opus 5.5 after a compaction when its
# current model came from a safeguards refusal fallback.
#
# A refusal fallback swaps the session to the fallback model for good. Compaction
# drops the context that got flagged, so it is the natural point to retry 5.5.
# No hook output can change the model, so the SessionStart(compact) hook types
# `/model` into the session's tmux pane, and the PreModelSwitch hook approves
# that one switch so no cache-miss confirm blocks an unattended session.
#
#   bash opus-repin.sh session-start   # SessionStart hook, matcher "compact"
#   bash opus-repin.sh pre-switch      # PreModelSwitch hook
set -u

TARGET=claude-opus-5-5
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/opus-repin"
input=$(cat)
sid=$(jq -r '.session_id // empty' <<<"$input")
[[ -n "$sid" ]] || exit 0
mkdir -p "$STATE"
log() { printf '%s %s %s\n' "$(date +%FT%T%z)" "${sid:0:8}" "$*" >> "$STATE/log"; }

# The bottom input line is empty (or shows only the placeholder hint).
input_empty() {
    local line
    line=$(tmux capture-pane -p -t "$1" 2>/dev/null | grep '^❯' | tail -1) || return 1
    [[ "$line" =~ ^❯[[:space:]]*$ || "$line" =~ ^❯\ Try\ \" ]]
}

case "${1:-}" in
pre-switch)
    [[ -f "$STATE/$sid" ]] || exit 0
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
    fallback=$(grep -a '"subtype":"model_refusal_fallback"' "$transcript" | tail -1)
    [[ -n "$fallback" ]] || exit 0
    [[ "$(jq -r '.originalModel // empty' <<<"$fallback")" == "$TARGET" ]] || exit 0
    # Only undo the fallback itself: a model the user picked afterwards stays.
    model=$(jq -r '.model // empty' <<<"$input")
    [[ "$model" == "$(jq -r '.fallbackModel // empty' <<<"$fallback")" ]] || exit 0
    touch "$STATE/$sid"
    log "compacted on $model after a $TARGET refusal; typing /model in $pane"
    (
        for _ in $(seq 120); do
            sleep 1
            input_empty "$pane" || continue
            tmux send-keys -t "$pane" -l "/model $TARGET"
            sleep 0.5
            tmux send-keys -t "$pane" Enter
            exit 0
        done
        rm -f "$STATE/$sid"
        log "input never empty in $pane; gave up"
    ) </dev/null >/dev/null 2>&1 &
    ;;
esac
exit 0
