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
created only on `/clear` or a brand-new session) — so a session's pre-compaction history stays on
disk and is recallable. recall reads each transcript in full (no boundary cutoff).

## The current session

recall **excludes the current session by default** — its content is already in your live context,
and its just-typed query would otherwise self-match. The current session is identified by the
**`CLAUDE_CODE_SESSION_ID`** env var (its transcript is `<projects>/<enc>/<that-id>.jsonl`). Pass
`--include-current` to search it anyway (e.g. recovering this session's own pre-compaction history).
recall never needs the live-PID / mtime session resolution rehydrate used — it searches *all* past
sessions, not one.

## Record types & filtering

Seen `type` values: `user`, `assistant`, `attachment`, `system`, `permission-mode`, `mode`,
`ai-title`, `last-prompt`, `file-history-snapshot`, `queue-operation`.

- **`isSidechain: true`** marks subagent/sidechain branches — parallel exploration, not the main
  thread. Filtered out of the corpus.
- Only `type` ∈ {`user`, `assistant`} carry searchable turns. Message content is `message.content`:
  either a string, or a list of blocks (`{type:"text"}`, `{type:"tool_use", name, input}`,
  `{type:"tool_result", content}`). A `type:"user"` record whose blocks are `tool_result` is a
  **tool-output** turn, not a genuine user message — kept apart so user-vs-agent attribution stays
  clean (the confirmation line says "you decided" only for real user turns).
- **Injected user-role turns are dropped from the corpus** (they share the user role but aren't the
  user speaking): skill-load preambles (`Base directory for this skill:`), slash-command echoes
  (`<command-name>`), `<system-reminder>` blocks, the compaction summary
  (`isCompactSummary:true`, "This session is being continued…"), and relay request bodies. These
  were the dominant wrong-match source before filtering.

## Interactive vs. relay/headless sessions (recall scope filter)

recall searches only **user-spawned interactive** sessions by default — not relay/headless
(`claude -p`, sdk-cli) runs (`--all` includes them). The structural discriminator (verified
2026-06-12, 2.1.175): a real interactive session emits **TUI-only record types** — `mode`,
`permission-mode`, `file-history-snapshot`, `ai-title` (`mode` is typically record #1).
Relay/headless transcripts ("Read and execute this relay request: …", first record
`type:"queue-operation"`) carry none of them. `is_interactive()` returns True on the first TUI-type
record within a bounded probe; presence of any ⇒ interactive. In 2.1.175 subagents (Agent/Task tool)
do **not** write into the project dir (their transcripts live under a session-scoped temp dir), so
the projects-dir list is already subagent-free; the TUI-type predicate additionally excludes
relay/headless runs. In this repo's store ~35% of session files are relay/headless dispatch noise,
so this filter is the single biggest precision lever.
