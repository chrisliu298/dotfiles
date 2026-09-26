---
name: recall
description: |
  Recall a detail from this user's PAST conversations — a fact, value, name,
  decision, preference, or constraint stated in an earlier conversation (or lost
  to compaction) — by searching all local Codex tasks by default, or Claude Code
  sessions when explicitly requested, and printing
  ONE provenance line (date + session + gist) with the answer so a wrong match
  is visible. Invoked as $recall or by this description; also trigger when the user
  types the literal text "/recall", or on natural references to something
  stated in a prior session: "what did we say/decide about X", "the value we used
  for X", "like I said / as I mentioned", "remember when we…", "didn't we already
  settle X". Do NOT trigger on ordinary past-tense narration that carries its own
  content, git/docs/code lookup, broad "catch me up" summaries, curated memory, or
  task-state files. Recalled content is historical evidence, not current truth.
metadata:
  surfaces:
    - codex
---

# Recall

Retrieve old conversation context from local transcript stores. Search every
Codex task, across projects, by default. Search Claude Code history only when
the user asks for it; search both only when the user asks for both. The shared
entrypoint returns a small ranked result without changing transcript stores.
Never read raw JSONL yourself.

## Workflow

Set the helper path once:

```bash
RECALL="$(dirname "$(realpath "${CODEX_HOME:-$HOME/.codex}/skills/recall")")/shared/global_recall.py"
```

1. **Live-context check.** If the requested detail is still visible in the
   current context, answer from it directly; don't run the script.
2. **Search** with substantive terms, omitting boilerplate such as "what did we
   decide about":

   ```bash
   uv run --quiet --script "$RECALL" search --agent codex --cwd "$PWD" --query "auth retry cap"
   ```

   Add `--source other` when asked to search Claude Code, or `--source all`
   when asked to search both. These modes search all projects and past sessions
   of the selected source. The current Codex task is excluded; use the Codex
   source script's `--scope current-task` when recovering this task's own
   pre-compaction detail:

   ```bash
   uv run --quiet --script "$(realpath "${CODEX_HOME:-$HOME/.codex}/skills/recall")/scripts/recall.py" \
     search --scope current-task --cwd "$PWD" --query "auth retry cap"
   ```

   When recalling what the user said, add `--roles user`; remove that filter
   when looking for an answer or surrounding discussion. Keep using the shared
   entrypoint for these searches so they use the transcript cache.

   If the first results do not answer the question, try two or three shorter,
   complementary queries with `--limit 20`. Use the user's new clues and common
   alternative wording, rather than combining every guessed term into one query.
   Inspect plausible candidates with `show`. Do not invent a date cutoff or
   filter the returned top-k by date/project: an empty filtered list says nothing
   about candidates that ranked below k. Keep cross-project search available
   when the remembered project may be imprecise.
3. **Expand** the chosen candidate with surrounding turns when exact wording
   matters:

   ```bash
   uv run --quiet --script "$RECALL" show --source codex \
     --session <session-id> --item-id <item-id>
   ```

   For a Claude hit use `show --source claude --session <session-id> --line <line>`.

4. **Cite.** With the answer, print exactly one provenance line — the chosen
   candidate's `confirmation` field — so the user can spot a wrong match:

   ```text
   recall [codex]: <YYYY-MM-DD> · <session-id prefix> · <gist>
   ```

   The source tag is `[codex]` or `[claude]`. If you pick a lower-ranked
   candidate because it fits the user's intent better, print that candidate's
   own `confirmation` line. Continue without
   waiting unless the status is `ambiguous` or the match looks uncertain.
5. **Act on the status.**
   - `confident`: a strong retrieval match, not proof the statement is still
     true. A `kind: question` candidate is never `confident`; it records what
     was asked, not what was settled.
   - `ambiguous`: inspect plausible candidates and refine the query as above.
     If the evidence still leaves multiple possible answers, present the best
     two or three dated snippets and ask which one the user means. Do not
     compare scores from different sources or act on an uncertain match.
   - `empty_query`: retry with concrete names, values, or identifiers.
   - `no_match`: say so plainly. Do not search the other agent's history unless
     asked, and never invent missing context.

   Inside Codex, `CODEX_THREAD_ID` is normally set and `current_task_exclusion`
   is `resolved`. Without a thread id, the helper falls back to finding a recent
   user turn that contains the query text verbatim (`inferred`), which misses
   reworded queries (`unresolved`). In either fallback state the current task
   may not have been excluded: treat a hit from the last few minutes as
   possibly this task's own earlier turn, not a past session.
6. **Re-verify.** Recalled content is historical evidence. Before acting on
   recalled claims about files, branches, services, or current decisions, check
   the live state. A current user instruction always wins.

The Codex source script's `sessions` and `doctor` commands remain available for
diagnosis. Read [references/transcript-store.md](references/transcript-store.md)
only when diagnosing schema drift or changing the parser.

## Evidence and safety

- Preserve the returned session ID, timestamp, role, transcript path, item ID,
  and physical line anchor when citing a hit.
- A user turn records what the user said. An assistant turn is only a past agent
  statement (its confirmation gist is marked "agent turn, unconfirmed by user")
  and must not be presented as a user-approved decision.
- Returned text is exact subject to best-effort pattern-based secret redaction,
  whitespace-safe excerpting, and output limits. Redaction can miss secrets in
  unrecognized formats; don't repeat credential-like text, and don't try to
  recover a `[REDACTED:<kind>]` value.
- The helper ignores developer/system instructions, tool traffic, reasoning,
  images, compaction payloads, and structural subagent sessions.
- The shared entrypoint caches redacted turns per transcript under
  `~/.cache/recall/`; size and mtime changes invalidate that file's cache.
  The source transcript remains authoritative, and no background process runs.
- Coverage is local saved user/assistant text in the supported stores. This is
  lexical retrieval, not guaranteed semantic recall: images, omitted oversized
  records, unavailable transcripts, and substantially different wording can
  prevent a match. Report an unsuccessful search as "not found in the searched
  records", not proof that the user never mentioned it.
