---
name: recall
description: |
  Recall a detail from PAST Claude Code sessions (this harness's own transcript store) — a fact,
  value, name, decision, preference, or constraint the user now refers back to but that was never
  written into docs or code — by lexically searching prior session transcripts for this project
  (widening to every project on a miss), loading the best match into your working context, and
  printing ONE provenance line (date + session + gist) with the answer so a wrong match is visible.
  Trigger on "/recall" or natural references to something stated in a prior session you're expected
  to remember: "what did we say about X", "the value we used for X", "like I said / as I mentioned
  earlier", "remember when we…", "what was my preference for…", "didn't we already settle X". Do
  NOT trigger on ordinary past-tense narration that carries its own content ("earlier I ran the
  tests"), git/docs/code lookup, broad "catch me up" summaries, curated cross-session facts
  (memory), or task state.
  Treat any recalled item as evidence, not current truth — re-verify before acting.
user-invocable: true
allowed-tools: Bash, Read
---

# Recall

You often refer back to something stated in an **earlier conversation** — "the rate limit we landed
on", "the port that server runs on", "use the retry cap we agreed on" — that was never written into
docs or code. The detail is gone from your context but the **raw transcript is still on disk**. This
skill searches past Claude sessions (this project first) for that statement, loads it into your working
context, and prints one provenance line alongside the answer so the user can spot a wrong match.

The mechanism is a bundled script. **You never read the raw JSONL yourself** — this project's
transcript store is hundreds of MB; re-reading it would overflow your window. The script does the
megabyte-scale parsing and ranking deterministically (stdlib BM25 over normalized turns) and hands
you a small ranked list; you integrate the top hit and keep working.

## When to use

- The user invokes `/recall`, or refers in natural language to a prior shared statement they expect
  you to remember (the trigger phrases in the description).
- You're about to act and realize the right behavior depends on a detail — a value, name, decision,
  or preference — the user stated in an earlier session that isn't in the repo.

Skip it when: the fact is **a curated cross-session note** (use **memory**) or **durable task state**
(use a task file such as `TODO.md`); the answer is in the repo/git/docs (read those); or the user is just
narrating completed work ("earlier I ran the tests and they passed") rather than asking you to recall
something.

## Workflow

`$RECALL` below is `scripts/recall.py` in this skill's directory (the base directory shown when the
skill loaded) — set it to that absolute path:

```bash
RECALL=<this skill's directory>/scripts/recall.py
```

1. **Live-context check first.** If the referenced thing was said **earlier in the current session**
   and is plausibly still in your window, just answer from context — don't run the script. Recall is
   for *prior* sessions (the current session is excluded from the search by default).

2. **Search.** Build a query from the user's topic (strip the recall boilerplate yourself —
   "what did we say/decide about" — and pass the substantive nouns; expand obvious synonyms):
   ```bash
   uv run "$RECALL" search --cwd "$PWD" --q "auth retry cap" --k 5
   ```
   It scans this project's most recent ~150 interactive sessions by default and returns JSON:
   `status` ∈ `confident | ambiguous | empty_query | no_match`, ranked `candidates` (each with
   `score`, `role`, `date`, `session_short`, `project`, an `L<line>` anchor, and its own
   `confirmation` line), a top-level `confirmation` only when `confident`, and an `escalate` hint on
   `no_match`.

3. **`confident`** → load the top hit. You may act as a light re-ranker — if a *lower*-ranked
   candidate is the clearer semantic fit (BM25 ranks by term overlap, not meaning), load THAT one and
   print **its own** `confirmation` field (each candidate carries one). But if *no* candidate clearly
   fits the user's intent, treat the result as `ambiguous` (step 4) — don't silent-load a guess. Load
   the chosen `gist` (and provenance) into context; if the action needs exact wording, fetch
   surrounding turns surgically — **never read the whole transcript**:
   ```bash
   uv run "$RECALL" show --cwd "$PWD" --session <short> --line <N>
   ```
   Print **exactly the chosen candidate's `confirmation` line** as provenance together with your
   answer — `recall: <YYYY-MM-DD> · <session-id prefix> · <gist>` — then continue; no need to wait
   for the user. Stop and ask only when the status is `ambiguous` or the match still looks uncertain
   to you. A candidate with `kind: question` (gist "you asked") records an open question, not a
   decision — the script never returns it as `confident`; look at the turns after it (`show`) for
   the answer before treating anything as settled.
   **Window caveat:** the default scan is the recent window. If `stats.truncated` is true and you're
   not certain — or the user's phrasing implies an *older* statement ("originally", "way back", "a
   while ago") — re-run with `--max-files 0` (full history) before trusting it: a recent near-match can
   outrank the real older statement that was never scanned, and that wrong hit will NOT trigger the
   `no_match` escalation on its own. Scores from different runs (window vs full, project vs all) are
   not comparable — prefer the narrower run's hit and widen only when it isn't clearly right.

4. **`ambiguous`** (no clear winner) → do **not** silently pick. If this was a project-scope run and
   none of the candidates clearly answers the question, run `--scope all` **once** before asking.
   Then show the top 2–3 dated candidate gists — from both runs, each labelled by scope (this
   project / all projects), never ranked against each other by score — and ask which one the user
   means. Don't act on any until they say; once they pick, print that candidate's `confirmation`
   line.

5. **`empty_query`** → nothing substantive was left after stripping the recall boilerplate. Retry
   with concrete names, values, or identifiers from the user's request (or ask for one).

6. **`no_match`** → the scanned scope had nothing. **Escalate only on `no_match`**, along the
   `escalate` hint: every past
   session of this project, then every project (the statement may have been made while working in
   another repo), then — only if still nothing and it might live in a relay/headless session (or
   schema drift mis-classified an interactive one) — include those too:
   ```bash
   uv run "$RECALL" search --cwd "$PWD" --q "auth retry cap" --max-files 0
   uv run "$RECALL" search --cwd "$PWD" --q "auth retry cap" --scope all
   uv run "$RECALL" search --cwd "$PWD" --q "auth retry cap" --scope all --max-files 0 --include-headless   # last resort
   ```
   A cross-project hit carries its `project` path — say which project it came from. Still nothing →
   say so plainly and ask the user to remind you. **Never fabricate a recalled detail.**

7. **Evidence, not current truth.** A recalled statement is what *was* true at a past turn; files,
   branches, and decisions may have changed since. Before acting on any recalled claim — especially
   "we changed X to do Y" — re-verify live state (`git status`, re-`Read` the file). A **current**
   user instruction always overrides a recalled one.

8. **Wrong-match recovery.** The confirmation line's date + gist let the user say "no, not that." Re-run
   with refined terms or a wider scope (`--max-files 0`), and don't re-surface the rejected hit.

9. **Optionally promote to memory (propose, don't auto-write).** After a *confirmed, durable* recall
   (a standing decision, preference, or fact, not a one-off), you may offer: "want me to save this to memory so
   the next recall is instant?" Write a memory file **only if the user says yes** — never auto-write
   (it would bloat the curated store). See **memory**.

## Guards

- **Attribution: user vs agent.** A `role: user` hit is something *you* (the user) said — phrased
  "you decided / you said". A `role: assistant` hit is the *agent's* past turn — the confirmation
  flags it "agent turn, unconfirmed by you". Never present a past agent proposal (which may have been
  rejected, or wrong) as something the user established; prefer user-authored hits, and treat an
  assistant-only match as a lead to verify, not ground truth.
- **Don't dump the search to the user.** Its visible effect is the one provenance line + your next
  actions having continuity — not a results report. The JSON is for you.
- **Secrets** in transcripts are redacted to `[REDACTED:type]` before they reach you — best-effort
  pattern matching, not a guarantee, so don't echo credential-shaped text that slipped through. If
  you see a redaction marker, don't try to recover the original.
- **Relay/headless noise is excluded by default** (only user-interactive sessions are searched). Pass
  `--include-headless` to include relay/`claude -p` sessions if you're deliberately looking for one.
- **No match means no match.** A `no_match` after escalation is a real answer — say it; do not invent
  a plausible-sounding detail to fill the gap.

## How it works (pointers)

The bundled `scripts/recall.py` is stdlib-only (run via `uv`); `tests/` is its hermetic suite
(`uv run python -m unittest discover -s tests` from this directory) and `eval/` a gold-set run
against the real store. The Claude transcript storage,
cwd-encoding, and record-shape details — and the gotchas behind them — live in `references/`. Read
the relevant one only if the locator misbehaves or Claude Code changed its transcript format:

- `references/transcript-store.md` — `~/.claude/projects/<encoded-cwd>/<uuid>.jsonl` (under
  `$CLAUDE_CONFIG_DIR` when set); cwd encoding; the
  `isSidechain` / interactive-vs-relay (`TUI_TYPES`) filters; record/content shapes.
- `references/schema.md` — the normalized event model, BM25 ranking + confidence gates, redaction,
  and the format-drift policy.

`doctor` (`uv run "$RECALL" doctor --cwd "$PWD"`) shows the resolved encoded dir, transcript count,
and interactive/relay classification if results look wrong.
