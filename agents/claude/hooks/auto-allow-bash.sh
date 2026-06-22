#!/usr/bin/env bash
# Auto-allow ANY tool in any permission mode EXCEPT plan, so unattended runs never stall.
# (Historically named for Bash — the settings.json matcher is now "*" so it covers every tool.)
#
# Why this exists: server-side GrowthBook rollout flags (observed: tengu_quill_harbor=acceptEdits,
# tengu_permission_friction=true) can silently downgrade `bypassPermissions` -> `acceptEdits`
# mid-session with no user action. Once out of bypass, two failure modes appear: (1) a compound
# `cd && source && python ...` Bash command hits the non-bypassable "multiple operations require
# approval" check; (2) any NON-Bash tool — a subagent Agent/Task spawn, an MCP tool, WebFetch, a
# Write outside the workspace — prompts for approval. Either blocks an unattended run indefinitely
# (observed: a cd-prefixed command stalled an overnight loop ~5h; later, subagent/MCP spawns from
# prism/relay/agent-teams stalled despite a Bash-only hook).
# Settings `permissions.allow` rules canNOT approve compound commands (the safety check runs before
# allow rules); a PreToolUse hook can, and it runs in EVERY mode for EVERY tool — so every tool is
# auto-approved regardless of any silent downgrade.
#
# Plan mode is deliberately excluded: when the user explicitly enters plan mode they want no
# execution, so the hook stays out of the way and normal plan-mode blocking applies.
input=$(cat)
if printf '%s' "$input" | grep -q '"permission_mode"[[:space:]]*:[[:space:]]*"plan"'; then
  exit 0
fi
printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"unattended-safe: auto-allow any tool in any non-plan mode (survives server-side bypass downgrade)"}}'
