---
name: keep-warm
description: |
  Schedule a 55-minute heartbeat that keeps Claude Code's 1-hour prompt cache from
  expiring during long unattended tasks. Use when starting a multi-hour run, or when the
  user says "keep cache warm", "warm cache", "stay warm", "heartbeat", "keep alive",
  or invokes "keep-warm". Pass "stop", "cancel", or "off" to cancel an active heartbeat.
allowed-tools: CronCreate, CronList, CronDelete, ScheduleWakeup
user-invocable: true
---

# Keep Warm

Schedules a recurring heartbeat every 55 minutes so the prompt cache is touched before its 60-minute TTL expires. Without this, idle gaps past 1 hour force the next turn to reprocess the entire context as fresh input — billed at full input rate against weekly usage.

## Why 55 minutes

5-minute safety margin against network latency, queueing, and clock drift. The 1-hour cache is the relevant tier (not the 5-minute default) — this skill assumes the user has `ENABLE_PROMPT_CACHING_1H=1` set.

## Start

1. Pick the best available scheduling tool in this session:
   - **CronCreate** (preferred): set-and-forget recurrence with cron expression `*/55 * * * *`.
   - **ScheduleWakeup** (fallback): one-shot `delaySeconds: 3300`. The heartbeat itself reschedules the next one before stopping.
2. Heartbeat prompt: `Cache heartbeat. Reply with one short line and stop. No file reads, no tool calls, no other action.`
3. Tag the schedule's reason field with `keep-warm heartbeat` so `stop` can find it.
4. Report to the user: scheduled, next fire time, and how to stop.

## Stop (arg: `stop`, `cancel`, `off`)

1. List active schedules with `CronList` (or equivalent).
2. Delete the one whose reason contains `keep-warm heartbeat`.
3. Confirm cancellation.

## Rules

- **One heartbeat per session.** Before scheduling, list existing schedules. If one tagged `keep-warm heartbeat` already exists, report it and skip — do not duplicate.
- **The heartbeat must be a no-op turn.** When it fires, do not start new work, read files, or invoke tools. One short line and stop.
- **Don't schedule for short tasks.** If the user's current task is clearly under 1 hour, tell them they don't need this and skip.
