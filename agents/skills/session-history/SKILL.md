---
name: session-history
description: |
  Search and retrieve exact, redacted conversational turns from this user's past
  Codex tasks, including context lost after compaction and discussions from much
  older sessions. Use when the user asks what was said, decided, attempted, or
  learned in an earlier Codex conversation. Codex-only; this is historical
  evidence retrieval, not durable memory or current-state verification.
metadata:
  surfaces:
    - codex
---

# Session History

Retrieve old Codex conversation context from the local rollout JSONL store. The
bundled script searches raw user and assistant turns without modifying Codex's
sessions, configuration, or databases.

## Workflow

Set the helper path once:

```bash
HISTORY="${CODEX_HOME:-$HOME/.codex}/skills/session-history/scripts/session_history.py"
```

1. If the requested detail is still visible in the current context, answer from
   it directly.
2. Otherwise search with substantive terms, omitting phrases such as "what did
   we decide":

   ```bash
   uv run --quiet --script "$HISTORY" search --cwd "$PWD" --query "auth retry cap"
   ```

   The default `auto` scope checks the current task, then this working directory,
   then all Codex sessions. Use `--scope current-task`, `current-project`, or
   `all` when the intended boundary is already clear.
3. For the chosen candidate, retrieve surrounding conversational turns:

   ```bash
   uv run --quiet --script "$HISTORY" show \
     --session-id <session-id> --item-id <item-id>
   ```

4. Treat `confident` as a strong retrieval match, not proof that the historical
   statement is still true. If results are `ambiguous`, present the best two or
   three dated snippets and ask which one the user means. If `empty_query`, retry
   with concrete names, values, or identifiers. If `no_match`, say so; never
   invent missing context.
5. Before acting on recalled claims about files, branches, services, or current
   decisions, verify the live state. A current user instruction always wins.

Use `sessions --cwd "$PWD"` to inspect candidate tasks when the user remembers
the task but not searchable wording. Use `doctor` when the transcript store or
current-task resolution appears unavailable.

## Evidence and safety

- Preserve the returned session ID, timestamp, role, transcript path, item ID,
  and physical line anchor when citing a hit.
- A user turn records what the user said. An assistant turn is only a past agent
  statement and must not be presented as a user-approved decision.
- Returned text is exact subject to explicit secret redaction, whitespace-safe
  excerpting, and output limits.
- The helper ignores developer/system instructions, tool traffic, reasoning,
  images, compaction payloads, and structural subagent sessions.
- Search is stateless by design: no daemon or persistent content index is
  created. Read [references/transcript-store.md](references/transcript-store.md)
  only when diagnosing schema drift or changing the parser.
