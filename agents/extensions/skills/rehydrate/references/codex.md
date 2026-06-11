# Codex transcript store (rollouts)

> Verified 2026-06-10 against real rollouts. A genuine `compacted` record was confirmed in an
> older rollout; recent ones on this machine were uncompacted. Schema is community-documented,
> not a formal contract — re-verify on format drift.

## Location

```
${CODEX_HOME:-~/.codex}/sessions/YYYY/MM/DD/rollout-<ISO-ts>-<uuid>.jsonl
```

**Date-bucketed, NOT cwd-encoded.** The cwd is *inside* the file. Also: `~/.codex/archived_sessions/`
(ignore unless no live match), `~/.codex/history.jsonl` (global prompt history).

## Identifying the current session

No documented session-id env var. So:

1. Enumerate recent `rollout-*.jsonl` (look back ~7 days, not just today — long/resumed sessions
   span midnight), sorted by **mtime** (never by filename: two rollouts can share the same
   ISO-second and differ only by uuid).
2. Read **line 1** of each candidate: `type:"session_meta"`, `payload:{id, cwd, timestamp, ...}`.
   Keep those where `realpath(session_meta.cwd) == realpath($PWD)`.
3. Pick the freshest by mtime. If the top two cwd-matches were modified within ~120s of each
   other, that's parallel sessions/subagents → **fail closed (AMBIGUOUS)**, don't guess.

**`forked_from_id`:** a forked rollout replays several `session_meta` records at the top, chained
by `forked_from_id`. The live session is the one whose `id` matches the filename uuid — use the
filename uuid as ground truth.

## Compaction boundary

- **`type:"compacted"`** (top-level) with `payload:{message, replacement_history:[...]}`. This is
  the real, structural boundary. `replacement_history` is the post-compaction context Codex now
  runs on.
- `event_msg` with `payload.type:"context_compacted"` fires right after — a UI echo, empty
  payload. Not the boundary.
- Weak textual hints (`compact_prompt`, `compact_token_limit`) appear inside ordinary tool
  outputs/prompts too — **never** treat them as the boundary on their own.

Use the **last** `compacted` record. Pre-compaction detail = `response_item` records before it.

⚠ **`replacement_history` is huge.** Repeated compaction + tool output has produced 700MB–2GB
rollouts (openai/codex#24948). The script streams line-by-line and *peeks the record type* on
oversized lines instead of full-parsing them — don't load `replacement_history` content.

## Record types

- Top-level `type`: `session_meta`, `turn_context`, `response_item`, `event_msg`, `compacted`.
- `response_item.payload.type`: `message` (has `role`+`content`), `agent_message`, `reasoning`
  (drop — verbose, low recovery value), `function_call` (name + JSON `arguments`; paths and
  `command` are inside the arguments string), `function_call_output`, `token_count` (drop).
- Extract file paths/commands by regex over the `function_call.arguments` string.
