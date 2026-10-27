---
name: agent-audit
description: Measure how Claude Code sessions and agents spend their turns from local transcripts (interruptions, cross-session messages, subagent/skill/agent-team/codex-exec use), and run baseline → one change → re-measure for workflow changes. Use to review, restructure or re-check an agent workflow.
user-invocable: true
allowed-tools: Bash, Read
---

# Agent audit

Workflow changes (splitting, merging or retiring sessions, delegation rules, review gates) are
judged by numbers from the transcripts, measured the same way before and after. The helper
does the counting; you do the judgment.

## Helper

`scripts/agent-audit` beside this file (resolve its installed location). Read-only, stdlib Python;
run it with `uv run --no-project python -I <path> ...` or directly.

```bash
agent-audit sessions   --project seedance-verifier-clf --since 2026-10-14       # titles, ranges, sizes
agent-audit sources    --project seedance-verifier-clf --title '^Lead' --by day  # what started each turn
agent-audit traffic    --project seedance-verifier-clf --since 2026-10-14       # SendMessage sender -> recipient
agent-audit delegation --project seedance-verifier-clf --since 2026-08-27 --cx  # subagents, skills, cx lines
```

`--project` matches a substring of the `~/.claude/projects` directory name, `--title` is a regex
on the session title, `--session` a session id prefix (repeatable). `--since/--until` are local
dates, inclusive. `--json` for machine-readable output.

`sources` columns: `user` (typed by the user), `peer` (another session's message; senders listed
below the table, `wt-*` are cx executor questions relayed by `cx ask`), `scheduled` (cron fires),
`task-receipt` (the session's own background work reporting back, not an outside interruption),
`compaction`, `system` (caveats, hook feedback, interrupts).

## Loop

1. **Baseline**: run the helper for the sessions and window the change would affect, and save the
   output with its command line in a scratch file or the project's records.
2. **Proposal**: name the concrete cost the numbers show and the smallest change that addresses
   it. Discuss with the affected sessions openly (give them the numbers and the user's words;
   let them challenge both). The user decides session-level changes.
3. **One change at a time**, then re-run the same commands over the window after it, with the
   same filters. Revert a change whose numbers got worse.

## Re-check after a change

Besides re-running the numbers, check each time:

- **Same clock window.** Compare days over the same hours (e.g. 00:00 to now on every day); a
  night after a change against a daytime before it shows nothing.
- **Why peer traffic moved.** Read the messages, not just the count: deliverables of work the
  session handed out are expected; pure receipts ("收到", "已登记") and status sync are the cost a
  routing change is meant to remove.
- **Each session's live crons against its role.** The latest `session_cron_carry` attachment
  lists the crons carried into the session; add `CronCreate` / `CronDelete` calls after it.
  Polling a session's role doc keeps out of it (a lead re-adding its own watch loop) is drift.
- **Retired sessions are gone.** Every session the plan closes has no tmux session and no
  process left.

## Counting rules the helper encodes

Check these before trusting a hand-rolled count:

- Mid-turn deliveries are `queued_command` attachments; turn-starting ones are `user` records.
  They are disjoint: count both, don't dedupe across them. Never dedupe by a text prefix — every
  peer message starts with the same wrapper.
- `origin.kind` (`human`, `peer`, `task-notification`) is the source. Cron fires are `isMeta`
  user records with no kind whose text equals a `CronCreate` / `session_cron_carry` prompt.
- Skip `tool_result` user records and `isSidechain` records; subagents live in
  `<session>/subagents/*.jsonl`.
- Titles come from `custom-title` records (the last one wins; renamed sessions report their final
  title).
- Each cx question has `ask-NNN.md` and `ask-NNN.md.sent`; count only the former.

For a number the helper does not produce, write the query in scratch, test it on one session you
can check by hand, and verify a few rows against the raw records before reporting it.
