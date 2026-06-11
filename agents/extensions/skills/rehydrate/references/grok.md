# Grok Build session store

> Verified 2026-06-10 against `~/.grok/docs/user-guide/17-sessions.md` + real session dirs.
> `updates.jsonl` always retains full history, so Grok is the easiest harness for *content* —
> the only hard part is picking the right session dir.

## Location

```
${GROK_HOME:-~/.grok}/sessions/<url-encoded-cwd>/<session-uuidv7>/updates.jsonl
```

cwd is **URL-encoded**: `/Users/you/code/app` → `%2FUsers%2Fyou%2Fcode%2Fapp` (Linux: `/home/you/...` → `%2Fhome%2Fyou%2F...`).
**Long-path fallback:** when the encoded name would exceed 255 bytes, Grok uses a slug+hash dir
and writes the real path into a `.cwd` sidecar inside the group — so on a miss, scan
`sessions/*/.cwd` for one whose contents equal `$PWD`.

Per-session dir contents: `updates.jsonl` (**authoritative**, append-only), `chat_history.jsonl`
(raw model input — ignore), `summary.json` (index), `plan.json` (TODO state),
`signals.json` (token/turn counters incl. `compactionCount`), `compaction_checkpoints/`,
`rewind_points.jsonl`, `subagents/`.

## Identifying the current session

1. **`GROK_SESSION_ID`** env (and `GROK_WORKSPACE_ROOT`) when present → use that uuidv7 dir.
2. Else, among the cwd group's child dirs, pick the one with the **max `summary.json` `updated_at`**
   whose `info.cwd` matches. `updated_at` beats raw mtime (Grok writes many sidecar files).
3. ⚠ **`~/.grok/active_sessions.json` is unreliable** — it was `[]` even with a live session. Do
   not depend on it.

`summary.json.parent_session_id` is fork/restore lineage — the recovery target is the current
leaf, **not** the parent. Don't follow it.

## Compaction detection

`updates.jsonl` is never truncated, so there's no in-stream "boundary" to find for *content*.
Detect *whether* compaction happened (else: nothing to rehydrate) via, in order:

1. `signals.json` → `compactionCount > 0` (clean boolean probe; also `totalTokensBeforeCompaction`).
2. `compaction_checkpoints/` non-empty (each checkpoint JSON carries `prompt_index_at_compaction`).

If neither, report `NO_COMPACTION`.

## Record shape (the load-bearing gotcha)

`updates.jsonl` lines are **JSON-RPC envelopes**, not flat-`type` records:

```json
{"method":"session/update","params":{"sessionId":"…","update":{"sessionUpdate":"<kind>", …}},"timestamp":…}
```

The discriminator is at **`.params.update.sessionUpdate`** — a parser that looks for a top-level
`type` field extracts nothing. Kinds seen: `user_message_chunk`, `agent_message_chunk`,
`agent_thought_chunk` (drop — reasoning), `tool_call`, `tool_call_update`, `plan`,
`available_commands_update` (**drop** — the full slash-command catalog, large + pure noise).
Message text is under `update.content` (string or `{text}`).
