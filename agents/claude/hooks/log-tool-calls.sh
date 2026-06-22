#!/usr/bin/env bash
# Diagnostic logger (TEMPORARY — remove once a stall is captured).
#
# Appends one tab-separated line per tool call: UTC timestamp, permission_mode, tool_name, and a
# truncated tool_input snippet. Runs alongside auto-allow-bash.sh on the PreToolUse "*" matcher.
# Purpose: the NEXT unattended stall becomes self-diagnosing — the LAST line in the log reveals
# whether the stalled call was:
#   - main-thread        -> the auto-allow hook covers it (matcher widening is the fix)
#   - subagent-internal  -> parent PreToolUse hooks do NOT fire inside spawned subagents
#                           (GitHub #34692 closed-not-planned, #21460, #27661); needs a
#                           subagent/skill-level hook instead
#   - an MCP "trust this server" / Elicitation dialog, or the rm -rf / · rm -rf ~ circuit breaker
#                           -> no hook can suppress these; needs pre-auth, not a hook
# Never blocks and never emits a permission decision: always exits 0 with no stdout, so the
# sibling auto-allow hook's decision stands.
input=$(cat)
log="${CLAUDE_TOOL_CALL_LOG:-$HOME/.claude/tool-calls.log}"
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
tool=$(printf '%s' "$input" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
mode=$(printf '%s' "$input" | grep -o '"permission_mode"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
snippet=$(printf '%s' "$input" | sed 's/.*"tool_input"[[:space:]]*:[[:space:]]*//' | tr '\n\t' '  ' | cut -c1-160)
printf '%s\t%s\t%s\t%s\n' "$ts" "${mode:-?}" "${tool:-?}" "$snippet" >>"$log" 2>/dev/null
exit 0
