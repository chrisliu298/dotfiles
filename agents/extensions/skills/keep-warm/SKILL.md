---
name: keep-warm
description: |
  Schedule a recurring heartbeat that keeps Claude Code's 1-hour prompt cache from
  expiring during long unattended tasks. Use when starting a multi-hour run, or when the
  user says "keep cache warm", "warm cache", "stay warm", "heartbeat", "keep alive",
  or invokes "keep-warm". Pass "stop", "cancel", or "off" to cancel an active heartbeat.
allowed-tools: CronCreate, CronList, CronDelete
user-invocable: true
---

# Keep Warm

Schedules a recurring heartbeat that touches the prompt cache before its 60-minute TTL expires. Without this, idle gaps past 1 hour force the next turn to reprocess the entire context as fresh input — billed at full input rate against weekly usage.

This skill assumes the user has `ENABLE_PROMPT_CACHING_1H=1` set (the 1-hour cache tier, not the 5-minute default).

## Cadence

Cron cannot express "every 55 minutes." `*/55 * * * *` does **not** mean every 55 min — `*/N` resets each hour, so `*/55` fires at minute 0 and 55, producing alternating 55-min and 5-min gaps. Any `*/N` where N does not divide 60 is broken the same way. **Do not use `*/55`.**

Two correct options:
- **`*/30 * * * *` via CronCreate** (default): uniform 30-min gaps, well under the 60-min TTL, set-and-forget. One extra heartbeat per hour vs. a 55-min cadence — cheap, since the heartbeat is a single short reply. **No chain risk:** cron keeps firing regardless of missed wake-ups.
- **`/loop 55m <heartbeat-prompt>`** (only if the user explicitly wants 55-min cadence): true 55 min via the `/loop` skill, which reschedules itself with `ScheduleWakeup` under the hood. Tradeoff: it's a self-rescheduling chain, so a dropped wake-up silently ends it.

Do **not** call `ScheduleWakeup` directly from this skill — it's gated to `/loop` dynamic mode and its `prompt` must be a `/loop` input.

## Start

1. Default to **CronCreate** with `*/30 * * * *`. Only use `/loop 55m` if the user explicitly asked for a 55-min cadence and accepts the chain-failure risk.
2. Heartbeat prompt: `Cache heartbeat. Reply with one short line and stop. No file reads, no tool calls, no other action.`
3. Tag the schedule's reason field with `keep-warm heartbeat` so `stop` can find it.
4. Report to the user: scheduled, cadence, next fire time, and how to stop.

## Stop (arg: `stop`, `cancel`, `off`)

1. List active schedules with `CronList` (or equivalent).
2. Delete the one whose reason contains `keep-warm heartbeat`.
3. Confirm cancellation.

## Rules

- **One heartbeat per session.** Before scheduling, list existing schedules. If one tagged `keep-warm heartbeat` already exists, report it and skip — do not duplicate.
- **The heartbeat must be a no-op turn.** When it fires, do not start new work, read files, or invoke tools. One short line and stop.
- **Don't schedule for short tasks.** If the user's current task is clearly under 1 hour, tell them they don't need this and skip.
