---
name: recall
description: |
  Recall a detail from this user's PAST Codex tasks — a fact, value, name,
  decision, preference, or constraint stated in an earlier conversation (or lost
  to compaction) — by searching the local Codex rollout transcripts and printing
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

Retrieve old Codex conversation context from the local rollout JSONL store. The
bundled script searches raw user and assistant turns without modifying Codex's
sessions, configuration, or databases, and returns a small ranked JSON result;
never read the rollout files yourself.

## Workflow

Set the helper path once:

```bash
RECALL="${CODEX_HOME:-$HOME/.codex}/skills/recall/scripts/recall.py"
```

1. **Live-context check.** If the requested detail is still visible in the
   current context, answer from it directly; don't run the script.
2. **Search** with substantive terms, omitting boilerplate such as "what did we
   decide about":

   ```bash
   uv run --quiet --script "$RECALL" search --cwd "$PWD" --query "auth retry cap"
   ```

   The default `auto` scope checks this working directory's past tasks and
   widens to all Codex tasks only when the project has no match; if a project
   result looks wrong, rerun with `--scope all`. The current task is excluded, except with `--scope current-task`,
   which searches only this task — use it when the detail was said earlier in
   this task but has been lost to compaction. Use `--scope current-project` or
   `all` when the intended boundary is already clear.
3. **Expand** the chosen candidate with surrounding turns when exact wording
   matters:

   ```bash
   uv run --quiet --script "$RECALL" show \
     --session-id <session-id> --item-id <item-id>
   ```

4. **Cite.** With the answer, print exactly one provenance line — the chosen
   candidate's `confirmation` field — so the user can spot a wrong match:

   ```text
   recall: <YYYY-MM-DD> · <session-id prefix> · <gist>
   ```

   If you pick a lower-ranked candidate because it fits the user's intent
   better, print that candidate's own `confirmation` line. Continue without
   waiting unless the status is `ambiguous` or the match looks uncertain.
5. **Act on the status.**
   - `confident`: a strong retrieval match, not proof the statement is still
     true. A `kind: question` candidate is never `confident`; it records what
     was asked, not what was settled.
   - `ambiguous`: if `auto` stopped at an ambiguous `current-project` result
     and no candidate clearly answers the question, run once more with
     `--scope all` before asking. Then present the best two or three dated
     snippets (from both runs, labelled by scope; don't compare their scores
     across runs) and ask which one the user means. Don't act on any of them
     until the user answers.
   - `empty_query`: retry with concrete names, values, or identifiers.
   - `no_match`: widen the scope if it was narrowed; then say so plainly. Never
     invent missing context.

   Inside Codex, `CODEX_THREAD_ID` is normally set and `current_task_exclusion`
   is `resolved`. Without a thread id, the helper falls back to finding a recent
   user turn that contains the query text verbatim (`inferred`), which misses
   reworded queries (`unresolved`). In either fallback state the current task
   may not have been excluded: treat a hit from the last few minutes as
   possibly this task's own earlier turn, not a past session.
6. **Re-verify.** Recalled content is historical evidence. Before acting on
   recalled claims about files, branches, services, or current decisions, check
   the live state. A current user instruction always wins.

Use `sessions --cwd "$PWD"` to inspect candidate tasks when the user remembers
the task but not searchable wording. Use `doctor` when the transcript store or
current-task resolution appears unavailable.

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
- Search is stateless by design: no daemon or persistent content index is
  created. Read [references/transcript-store.md](references/transcript-store.md)
  only when diagnosing schema drift or changing the parser.
