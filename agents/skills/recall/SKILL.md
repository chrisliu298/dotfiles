---
description: |
  Recall a detail from THIS project's PAST Claude sessions — a fact, value, name, decision,
  preference, or constraint the user now refers back to but that was never written into docs or
  code — by lexically searching all prior session transcripts for this cwd, loading the best match
  into your working context, and printing ONE confirmation line (date + session + gist) so a wrong
  match is caught before you act. Trigger on "/recall" or natural references to something stated in a
  prior session you're expected to remember: "what did we say about X", "the value we used for X",
  "like I said / as I mentioned earlier", "remember when we…", "what was my preference
  for…", "didn't we already settle X". Do NOT trigger on
  ordinary past-tense narration that carries its own content ("earlier I ran the tests"), git/docs/code
  lookup, broad "catch me up" summaries, curated cross-session facts (memory), or task state (todo).
  Treat any recalled item as evidence, not current truth — re-verify before acting.
user-invocable: true
allowed-tools: Bash, Read
---

# Recall

You often refer back to something stated in an **earlier conversation** — "the rate limit we landed
on", "the port that server runs on", "use the retry cap we agreed on" — that was never written into
docs or code. The detail is gone from your context but the **raw transcript is still on disk**. This
skill searches this project's past Claude sessions for that statement, loads it into your working
context, and prints one confirmation line so the user can catch a wrong match before you act on it.

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
(use **todo** / `TODO.md`); the answer is in the repo/git/docs (read those); or the user is just
narrating completed work ("earlier I ran the tests and they passed") rather than asking you to recall
something.

## Workflow

```bash
RECALL=~/dotfiles/agents/skills/recall/scripts/recall.py
```

1. **Live-context check first.** If the referenced thing was said **earlier in the current session**
   and is plausibly still in your window, just answer from context — don't run the script. Recall is
   for *prior* sessions (the current session is excluded from the search by default).

2. **Search.** Build a query from the user's topic (strip the recall boilerplate yourself —
   "what did we say/decide about" — and pass the substantive nouns; expand obvious synonyms):
   ```bash
   uv run "$RECALL" search --cwd "$PWD" --q "auth retry cap" --k 5
   ```
   It scans the most recent ~150 interactive sessions by default (≈2–3s) and returns JSON:
   `status` ∈ `confident | ambiguous | no_match`, a pre-formatted `confirmation` line, and ranked
   `candidates` (each with `score`, `role`, `date`, `session_short`, and an `L<line>` anchor).

3. **`confident`** → load the top hit. You may act as a light re-ranker — if a *lower*-ranked
   candidate is the clearer semantic fit (BM25 ranks by term overlap, not meaning), load THAT one and
   print **its own** `confirmation` field (each candidate carries one). But if *no* candidate clearly
   fits the user's intent, treat the result as `ambiguous` (step 4) — don't silent-load a guess. Load
   the chosen `gist` (and provenance) into context; if the action needs exact wording, fetch
   surrounding turns surgically — **never read the whole transcript**:
   ```bash
   uv run "$RECALL" show --cwd "$PWD" --session <short> --line <N>
   ```
   Print **exactly the chosen candidate's `confirmation` line** — nothing more — then continue.
   **Window caveat:** the default scan is the recent window. If `stats.truncated` is true and you're
   not certain — or the user's phrasing implies an *older* statement ("originally", "way back", "a
   while ago") — re-run with `--max-files 0` (full history) before trusting it: a recent near-match can
   outrank the real older statement that was never scanned, and that wrong hit will NOT trigger the
   `no_match` escalation on its own.

4. **`ambiguous`** (no clear winner) → do **not** silently pick. Show the top 2–3 candidate gists +
   dates and ask which one the user means. Don't act on either until they say.

5. **`no_match`** → the default window had nothing. **Escalate**: first every past interactive
   session, then — only if still nothing and the statement might live in a relay/headless session (or
   schema drift mis-classified an interactive one) — include those too:
   ```bash
   uv run "$RECALL" search --cwd "$PWD" --q "auth retry cap" --max-files 0
   uv run "$RECALL" search --cwd "$PWD" --q "auth retry cap" --max-files 0 --all   # last resort
   ```
   Still nothing → say so plainly and ask the user to remind you. **Never fabricate a recalled
   detail.**

6. **Evidence, not current truth.** A recalled statement is what *was* true at a past turn; files,
   branches, and decisions may have changed since. Before acting on any recalled claim — especially
   "we changed X to do Y" — re-verify live state (`git status`, re-`Read` the file). A **current**
   user instruction always overrides a recalled one.

7. **Wrong-match recovery.** The confirmation line's date + gist let the user say "no, not that." Re-run
   with refined terms or a wider scope (`--max-files 0`), and don't re-surface the rejected hit.

8. **Optionally promote to memory (propose, don't auto-write).** After a *confirmed, durable* recall
   (a standing decision, preference, or fact, not a one-off), you may offer: "want me to save this to memory so
   the next recall is instant?" Write a memory file **only if the user says yes** — never auto-write
   (it would bloat the curated store). See **memory**.

## Guards

- **Attribution: user vs agent.** A `role: user` hit is something *you* (the user) said — phrased
  "you decided / you said". A `role: assistant` hit is the *agent's* past turn — the confirmation
  flags it "agent turn — unconfirmed by you". Never present a past agent proposal (which may have been
  rejected, or wrong) as something the user established; prefer user-authored hits, and treat an
  assistant-only match as a lead to verify, not ground truth.
- **Don't dump the search to the user.** Its visible effect is the one confirmation line + your next
  actions having continuity — not a results report. The JSON is for you.
- **Secrets** in transcripts are redacted to `[REDACTED:type]` before they reach you. If you see a
  redaction marker, don't try to recover the original.
- **Relay/headless noise is excluded by default** (only user-interactive sessions are searched). Pass
  `--all` to include relay/`claude -p` sessions if you're deliberately looking for one.
- **No match means no match.** A `no_match` after escalation is a real answer — say it; do not invent
  a plausible-sounding detail to fill the gap.

## How it works (pointers)

The bundled `scripts/recall.py` is stdlib-only (run via `uv`). The Claude transcript storage,
cwd-encoding, and record-shape details — and the gotchas behind them — live in `references/`. Read
the relevant one only if the locator misbehaves or Claude Code changed its transcript format:

- `references/claude.md` — `~/.claude/projects/<encoded-cwd>/<uuid>.jsonl`; cwd encoding; the
  `isSidechain` / interactive-vs-relay (`TUI_TYPES`) filters; record/content shapes.
- `references/schema.md` — the normalized event model, BM25 ranking + confidence gates, redaction,
  and the format-drift policy.

`doctor` (`uv run "$RECALL" doctor --cwd "$PWD"`) shows the resolved encoded dir, transcript count,
and interactive/relay classification if results look wrong.
