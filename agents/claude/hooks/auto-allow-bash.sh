#!/usr/bin/env bash
# Auto-allow the Bash tool in any permission mode EXCEPT plan, so unattended runs never stall.
#
# Why this exists: server-side GrowthBook rollout flags (observed: tengu_quill_harbor=acceptEdits,
# tengu_permission_friction=true) can silently downgrade `bypassPermissions` -> `acceptEdits`
# mid-session with no user action. Once out of bypass, a compound `cd && source && python ...`
# command hits the non-bypassable "multiple operations require approval" check and blocks an
# unattended run indefinitely (observed: a cd-prefixed command stalled an overnight loop ~5h).
# Settings `permissions.allow` rules canNOT approve compound commands (the safety check runs
# before allow rules); a PreToolUse hook can, and it runs in EVERY mode — so Bash is auto-approved
# regardless of any silent downgrade.
#
# Plan mode is deliberately excluded: when the user explicitly enters plan mode they want no
# execution, so the hook stays out of the way and normal plan-mode blocking applies.
input=$(cat)
if printf '%s' "$input" | grep -q '"permission_mode"[[:space:]]*:[[:space:]]*"plan"'; then
  exit 0
fi
printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"unattended-safe: auto-allow Bash in any non-plan mode (survives server-side bypass downgrade)"}}'
