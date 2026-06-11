# Claude Code transcript store

> Verified on this machine 2026-06-10, Claude Code ~2.1.x. The JSONL schema is **undocumented**
> (see anthropics/claude-code#53516) and drifts — re-verify shapes if the locator misbehaves.

## Location & cwd encoding

```
~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl
```

Encoding: replace **both** `/` and `.` with `-` on the absolute cwd. The leading `/` becomes a
leading `-`.

```
/Users/you/code/app             -> -Users-you-code-app
/home/you/code/app              -> -home-you-code-app          (Linux home: same rule, /home not /Users)
/Users/you/proj/.config/ghostty -> -Users-you-proj--config-ghostty   (note "/." -> "--")
```

The encoding is **lossy and non-invertible** (two distinct cwds can collide). Always
*forward-encode* the known `$PWD`; never try to decode a project-dir name back to a path.

One JSONL per session. `/compact` and auto-compact **continue in the same file** (a new file is
created only on `/clear` or a brand-new session).

## Identifying the current live session (priority order)

1. **`CLAUDE_CODE_SESSION_ID`** env var → open `<projects>/<enc>/<that-id>.jsonl` directly. This
   is the clean path and removes the "which sibling?" ambiguity entirely.
2. **PID map** `~/.claude/sessions/<pid>.json` → `{pid, sessionId, cwd, status, startedAt}`.
   Filter to `cwd == $PWD`; prefer the entry whose `pid` is in this process's ancestry (walk
   `ps -o ppid=` up from `$PPID`); else newest by mtime. These files exist only while the
   process is alive.
3. **mtime fallback** — newest `*.jsonl` in the project dir. Low confidence; flag it. A busy cwd
   has many siblings (subagents, parallel windows), so never *start* here.

## Compaction boundary (match a SET, not one marker)

Two real shapes have been observed; match any of them and take the **last** occurrence (a long
session can compact more than once):

- `type:"system", subtype:"compact_boundary"` — carries
  `compactMetadata:{trigger:"manual"|"auto", preTokens, postTokens, preservedSegment:{headUuid,anchorUuid,tailUuid}}`.
  Immediately followed by the summary record:
- `type:"user", isCompactSummary:true, isVisibleInTranscriptOnly:true` — the
  "This session is being continued…" summary text.
- `type:"system", subtype:"away_summary"` — an alternate/auto summary record with a `content`
  string. Treat it as a boundary too.

Pre-compaction raw detail = every record **before** the last boundary line. (`parentUuid` of the
summary record == `uuid` of the last pre-compaction record, if you need to verify the seam.)

## Record types & filtering

Seen `type` values: `user`, `assistant`, `attachment`, `system`, `permission-mode`, `mode`,
`ai-title`, `last-prompt`, `file-history-snapshot`, `queue-operation`.

- **`isSidechain: true`** marks subagent/sidechain branches — often the *majority* of records
  (43/64 in one sample). Filter these out of the broad pass by default; they're parallel
  exploration, not the main thread.
- Drop `attachment` (skill listings — multi-KB, already in context), `permission-mode`, `mode`,
  `ai-title`, `file-history-snapshot` as bookkeeping noise.
- Message content is `message.content`: either a string, or a list of blocks
  (`{type:"text"}`, `{type:"tool_use", name, input}`, `{type:"tool_result", content}`). File
  paths live in `tool_use.input.{file_path,path,notebook_path}`; Bash commands in
  `tool_use.input.command` when `name=="Bash"`.
