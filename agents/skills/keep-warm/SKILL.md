---
effort: low
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

Only cron `*/N` patterns where **N divides 60** produce uniform gaps — i.e. 15, 20, 30, 60. Anything else (`*/55`, `*/45`, `*/40`, `*/25`) resets at the top of each hour and produces a broken alternating pattern. **`*/55` is the canonical trap: it fires at :00 and :55, giving 55-min then 5-min gaps.**

`/loop <interval>` also uses cron under the hood for interval mode, so `/loop 55m` is broken the same way — do not suggest it as a workaround. (`/loop` dynamic mode, invoked with no interval, uses `ScheduleWakeup` and can pick any delay in [60s, 3600s] — but that's an active self-paced loop, not a passive heartbeat, and isn't appropriate for keep-warm.)

**True 55-min cadence is not reachable for keep-warm purposes.** Pick a cron-friendly cadence instead:

- **`*/30 * * * *`** (default): uniform 30-min gaps, well under the 60-min TTL. One extra heartbeat per hour vs. a hypothetical 55-min cadence — cheap, since the heartbeat is a single short reply.
- **`*/20 * * * *`** or **`*/15 * * * *`**: tighter cadences if extra safety margin is wanted.
- **Avoid `0 * * * *`** (every 60 min): fires *at* the TTL boundary, leaving zero margin for delivery jitter.

Do **not** call `ScheduleWakeup` directly from this skill — it's gated to `/loop` dynamic mode and its `prompt` must be a `/loop` input.

## Start

1. Use **CronCreate** with `*/30 * * * *`. If the user explicitly asks for "every 55 minutes" or another non-divisor cadence, tell them it's not expressible cleanly and offer the nearest divisor (30 or 60-but-risky) — do **not** silently substitute or use `/loop 55m`.
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
