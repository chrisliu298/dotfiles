---
name: agent-audit
description: Measure how Claude Code sessions and agents spend their turns (who interrupts whom, cross-session message traffic, subagent / skill / agent-team / codex-exec use) from local transcripts, and run the baseline → one change → re-measure loop for multi-agent workflow changes. Use when the user wants to review, restructure or re-check an agent workflow, or asks how much an agent is interrupted or delegates.
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
