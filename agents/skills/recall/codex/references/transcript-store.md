# Codex transcript store

This reference documents the local, undocumented schema used by
`scripts/recall.py`. Re-check it after a Codex update if `doctor`
reports files but few or no recognized messages.

## Location and source of truth

Codex rollout transcripts are append-oriented JSONL files under:

```text
${CODEX_HOME:-$HOME/.codex}/sessions/YYYY/MM/DD/rollout-*.jsonl
```

The helper is strictly read-only. It does not use or modify Codex-owned SQLite
databases, and it never rewrites transcript files.

## Observed records

Verified locally on 2026-09-09 with Codex CLI 0.153.4:

- Envelope: `timestamp`, `ordinal`, `type`, `payload`.
- `session_meta`: `payload.id`, `cwd`, `originator`, `thread_source`, optional
  `git.branch`, and `context_window.window_id`.
- Conversation: `type=response_item`, `payload.type=message`, role `user` or
  `assistant`, and content blocks `input_text` or `output_text`.
- Compaction: `type=compacted`, with window lineage and replacement history.
  Original pre-compaction turns normally remain in the rollout store; the
  helper searches originals and does not index replacement history.

Developer messages, tool calls/results, encrypted reasoning, images,
`event_msg`, `world_state`, token records, and compaction records are excluded.
Structural sources whose `thread_source` identifies a subagent, automation,
headless exec, or inter-agent run are excluded from ordinary searches.

One logical task can span multiple rollout files. Files are grouped using the
first `session_meta.payload.id`, which owns the physical rollout. A structural
subagent rollout can contain a later replayed parent `session_meta`; that replay
does not change the file's ownership. Item IDs plus transcript-relative line
numbers provide result anchors. `CODEX_THREAD_ID` and `CODEX_SESSION_ID` are
used, when available, to resolve the current task; otherwise a user turn in a
file modified within the last five minutes of wall-clock time that contains
the query text verbatim identifies it. The task is excluded from `auto`, `current-project`, and `all`
searches; `current-task` searches only it, excluding just the invoking turn.
`current_task_exclusion` reports `resolved`, `inferred` (the verbatim-query
guess), or `unresolved`. The fallback applies only when no thread id is
available, and it misses the current task whenever the query was reworded
(e.g. boilerplate stripped), so `unresolved` is expected outside Codex.

`auto` widens from the current project to all history only on `no_match`:
BM25 scores depend on corpus statistics, so hits ranked against different
corpora are not compared. Files parsed for the project pass are reused by the
`all` pass. `CODEX_RECALL_ROOT` (or `--root`) overrides the
sessions directory for tests.

Machine-injected pseudo-user blocks are excluded. When a user turn begins with
`## Referenced chats with Codex:` or `# Files mentioned by the user:`, the
parser discards that injected preamble and keeps the text after `## My request:`.
For response annotations, it retains only the user's annotation comments and
trailing request, not the selected assistant text or annotation boilerplate.

## Bounded parsing

The store can contain extremely large one-line payloads such as image data or
tool output. The parser caps each physical `readline`, drains oversized records
without decoding them, and reports omission counts. Malformed or incomplete
records are skipped and surfaced in search statistics rather than crashing the
retrieval.

## Privacy

Only short, redacted result excerpts leave the parser. Redaction is best-effort
and pattern-based: common API keys, bearer tokens, JWTs, private-key blocks
(to the end of the turn when the END line is missing), environment-secret
assignments, and long data/base64 runs are replaced with `[REDACTED:<kind>]`
before output. Secrets in unrecognized formats can pass through.
