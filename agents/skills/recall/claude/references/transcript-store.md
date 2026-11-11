# Claude Code transcript store

> Verified on this machine 2026-06-10, Claude Code ~2.1.x; queued attachments, `origin`, subagent and spill layout re-checked 2026-11-11. The JSONL schema is **undocumented**
> (see anthropics/claude-code#53516) and drifts — re-verify shapes if the locator misbehaves.

## Location & cwd encoding

```
~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl      ($CLAUDE_CONFIG_DIR/projects/... when set)
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

`search` and `grep` **exclude the current session by default** — its content is already in your
live context, and its just-typed query would otherwise self-match. The current session is identified
by the **`CLAUDE_CODE_SESSION_ID`** env var (its transcript is `<projects>/<enc>/<that-id>.jsonl`).
`--session current` searches it anyway (e.g. recovering this session's own pre-compaction history);
`session current`, `open` and `timeline` always include it. Lines printed by recall itself start
with `⟦recall⟧`, and `grep` drops items carrying that marker or a `recall` invocation.
recall never needs the live-PID / mtime session resolution rehydrate used — it searches *all* past
sessions, not one.

## Record types & filtering

Seen `type` values: `user`, `assistant`, `attachment`, `system`, `permission-mode`, `mode`,
`ai-title`, `last-prompt`, `file-history-snapshot`, `queue-operation`.

Session titles come from `ai-title` (`aiTitle`, regenerated as the session goes) and
`custom-title` (`customTitle`, a user `/rename`); `session_title()` takes the latest rename, else
the latest generated title. Codex thread names live in `~/.codex/session_index.jsonl`
(`id`, `thread_name`; later rows are renames).

- **`isSidechain: true`** marks subagent/sidechain branches — parallel exploration, not the main
  thread. Filtered out of the corpus.
- Messages come from `type` ∈ {`user`, `assistant`} and from queued attachments (below). Message
  content is `message.content`: either a string, or a list of blocks (`{type:"text"}`,
  `{type:"tool_use", name, input}`, `{type:"tool_result", content}`). A `type:"user"` record whose
  blocks are `tool_result` is a **tool-output** turn, not a genuine user message. The index holds
  messages only; `grep`/`open`/`session` read `tool_use` blocks as `command` items and
  `tool_result` blocks as `output` items straight from the transcript (`shared/items.py`).
- **Mid-turn messages** (typed while the agent was working) are not `type:"user"` records but
  `type:"attachment"` with `attachment.type:"queued_command"` and the text in `attachment.prompt`;
  `queue-operation` records duplicate it and are ignored.
- **Who spoke** — `speaker()` in `scripts/recall.py`, from the record's (or attachment's)
  `origin.kind` and text: `human` → `user`; `peer`/`channel`, or text opening with "Another Claude
  session sent a message", `<cross-session-message`, `<agent-message`, `<channel ` or
  `<teammate-message` → `peer`; `task-notification` and other non-human kinds → dropped.
  `isMeta:true` or `promptSource` `system`/`sdk` (hook feedback, scheduled prompts) → `automated`,
  as is a `human` prompt another tool typed (`# ` brief, `你是独立`/`你是新的`, `这个会话刚被重启`,
  `[cx `; agent-audit's `AUTOMATED` rule — on 2026-11-11 all 261 human-origin `# ` messages were a
  session's first, tool-sent brief). A slash command keeps `/<name> <args>` when its
  `<command-args>` is non-empty. An `AskUserQuestion` result (call id seen, or
  `toolUseResult.answers`) is the user's answer unless `is_error` (a blocking hook). Inside a
  subagent transcript every user-role message is the parent agent's, so `peer`.
- **Events** (`event` items, not indexed): `type:"system"` records (`subtype`, `content`) and the
  compaction summary (`isCompactSummary`, shown as `compacted`).
- **Spilled tool results**: an oversized `tool_result` keeps a `<persisted-output>` preview naming
  `<projects>/<enc>/<session>/tool-results/<id>.txt`; `grep` searches those files and
  `open REF --full` pages the full text. Subagent transcripts live at
  `<projects>/<enc>/<session>/subagents/agent-<id>.jsonl` with an `agent-<id>.meta.json` beside them
  (`agentType`, `description`, …); `session ID --children` lists them.
- **Injected user-role turns are dropped from the corpus** (they share the user role but aren't the
  user speaking): skill-load preambles (`Base directory for this skill:`), slash-command echoes
  (`<command-name>`, `<command-message>`), background-task notices (`<task-notification>`), local
  command output (`<local-command-stdout>`, `<local-command-caveat>`), `<system-reminder>` blocks, the compaction summary
  (`isCompactSummary:true`, "This session is being continued…"), and relay request bodies. These
  were the dominant wrong-match source before filtering.

## Interactive vs. relay/headless sessions (recall scope filter)

recall searches only **user-spawned interactive** sessions by default — not relay/headless
(`claude -p`, sdk-cli) runs (`--include-headless` includes them). The structural discriminator (verified
2026-06-12, 2.1.175): a real interactive session emits **TUI-only record types** — `mode`,
`permission-mode`, `file-history-snapshot`, `ai-title` (`mode` is typically record #1).
Relay/headless transcripts ("Read and execute this relay request: …", first record
`type:"queue-operation"`) carry none of them. `is_interactive()` returns True on the first TUI-type
record within a bounded probe; presence of any ⇒ interactive. Subagent transcripts sit one level
deeper (`<session>/subagents/`), so the `*/*.jsonl` listing the index uses is subagent-free; the
TUI-type predicate additionally excludes relay/headless runs. In this repo's store ~35% of session files are relay/headless dispatch noise,
so this filter is the single biggest precision lever.
