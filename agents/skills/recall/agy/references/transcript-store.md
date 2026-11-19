# agy transcript store

The local, undocumented schema `scripts/recall.py` and `shared/items.py` read. Verified
2026-11-19 with Antigravity CLI 1.5.12; re-check it after an agy update if recall finds
conversations but few or no messages.

## Location

```text
~/.gemini/antigravity-cli/                                 (AGY_RECALL_ROOT overrides it, for tests)
  brain/<conversation-uuid>/.system_generated/logs/transcript_full.jsonl   one step per line
  conversation_summaries.db                                titles, workspaces, subagent parents
  cache/last_conversations.json                            workspace path -> latest conversation
```

`transcript.jsonl` beside `transcript_full.jsonl` is a shorter copy and is not read;
`conversations/<uuid>.db` holds the same steps as protobuf blobs and is not read either. Refs use
physical line numbers of `transcript_full.jsonl`. Everything is opened read-only; the summaries
database is opened with `mode=ro`.

`conversation_summaries.conversation_summaries` gives `title` (empty until agy names the
conversation), `workspace_uris` (a JSON list of `file://` URIs; the first is the project) and
`parent_conversation_id` (set for a subagent). A conversation missing there takes its project
from `last_conversations.json`, the shortest workspace path naming it. The current conversation
is `ANTIGRAVITY_CONVERSATION_ID`, set in agy's `run_command` shells; it also makes agy the
`self` source.

## Steps

Each line: `step_index`, `source`, `type`, `status`, `created_at` (ISO, UTC), `content`, and
optionally `thinking`, `tool_calls` (`name`, `args` as a JSON string or an object), `error`,
`model` and token counts.

| type | becomes |
|---|---|
| `USER_INPUT` | `user` message: the text inside `<USER_REQUEST>`; the `<ADDITIONAL_METADATA>` and `<USER_SETTINGS_CHANGE>` blocks are dropped. A prompt a tool typed (same prefixes as the Claude build) is `automated` |
| `PLANNER_RESPONSE` | `assistant` message from `content` when not empty, then one `command` per tool call (block 1, 2, …): `run_command` → `CommandLine`, `read_file` → `Path`, `write_file`/`edit_file` → path and text, others their JSON arguments. `thinking` is never read |
| `GENERIC` | `output` (a tool's result) without the leading `Created At:`/`Completed At:` lines; `status` `ERROR` or an `error` field marks it an error; `RUNNING` is a background task's start notice |
| `SYSTEM_MESSAGE` | the body of the `<SYSTEM_MESSAGE>` block after agy's preamble, up to the final closing tag. `[Message] timestamp=… sender=S priority=… content=TEXT` is a pushed message: `automated` when S is one of this conversation's tasks (`<uuid>/task-N`: task results, scheduled prompts) or a `sender=system` `[Notice]`, else `peer` (agent-msg notices, relayed answers, a parent's brief to a subagent). Anything else (SessionStart or PreInvocation hook text) is a `system` event |
| `CHECKPOINT` | `compacted` event (agy's compaction summary) |
| `ERROR_MESSAGE` | `error` event from the `error` field (API failures) |

The index holds the messages (all four roles); `grep`, `session` and `open` read every item
straight from the transcript. The file is append-only; a last line without its newline is still
being written and is picked up on the next pass.
