# Muse transcript store

This reference documents the local, undocumented schema used by
`scripts/recall.py`. Re-check it after a Muse update if `doctor`
reports files but few or no recognized messages.

## Location and source of truth

Muse retained sessions are append-oriented JSONL files under:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/muse/sessions/YYYY/MM/DD/<session-id>/session.jsonl
```

Subagent sessions live under the parent session's `subagent/` directory and
are excluded from ordinary searches. The helper is strictly read-only.

## Observed records

Verified locally on 2026-10-13 with Muse Code 1.4.7:

- Envelope: `sequence`, `recorded_at` (microseconds since the epoch),
  `stream` (`{kind: "session", id}`), `payload_type`, `payload`.
- Workspace: `payload_type=runtime.session.metadata` carries
  `payload.workspace_root` (or `payload.record.workspace_root`); a
  `context_projection_checkpoint` event may repeat it.
- User turn: `payload.kind=run` with `payload.event.kind=started` and a
  string `payload.event.prompt`.
- Assistant turn: `payload.event.kind=assistant_message_committed` with a
  string `payload.event.text`.

Tool calls/results, approvals, compaction, permission transactions, and any
other record kinds are skipped. The session identity is the directory name
holding `session.jsonl`. `MUSE_SESSION_ID`, `MUSE_THREAD_ID`, and
`MUSE_CURRENT_SESSION_LOG` resolve the current session, which is excluded
from search unless scope `current-task` is requested. `MUSE_RECALL_ROOT`
(or `--root`) overrides the sessions directory for tests.

## Bounded parsing

Lines above 2 MB and malformed or incomplete records are skipped and counted
in search statistics rather than crashing retrieval. Unknown record kinds are
ignored, so a Muse update that adds record types degrades coverage
visibly instead of breaking the parser.

## Privacy

Only short, redacted result excerpts leave the parser. Redaction is best-effort
and pattern-based, using the same pattern set as the Claude/Codex builds:
common API keys, Bearer tokens, JWTs, private-key blocks, environment-secret
assignments, and long data/base64 runs are replaced with `[REDACTED:<kind>]`
before output. Secrets in unrecognized formats can pass through.
