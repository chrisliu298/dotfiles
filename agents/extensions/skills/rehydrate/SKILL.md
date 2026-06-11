---
effort: low
description: |
  Recover detail that a context compaction dropped, by reading the raw transcript of the
  CURRENT just-compacted session on disk and rehydrating your own working context with the
  decisions, exact file paths, errors, user corrections, and open threads the summary lost.
  Use right after a compaction / auto-compact when you're continuing prior work and the
  summary feels thin or you're about to re-derive something. Also trigger on "rehydrate",
  "/rehydrate", "recover context", "what did we decide about X", "what was the last error",
  "what were we doing before the summary". Detects Claude Code / Codex / Grok and reads that
  harness's own transcript store. Do NOT use on a fresh session with no prior work, for
  curated cross-session facts (that's memory), durable task state (that's todo / TODO.md), or
  plain session resume (codex resume / grok --resume) — this is raw-transcript recovery of the
  live session only.
user-invocable: true
---

# Rehydrate

Compaction trades detail for space: the harness replaces the raw history with a lossy summary
and continues. The summary reliably drops the things that are most expensive to re-derive —
exact file paths, *why* a decision was made, approaches already ruled out, the precise error
that caused a pivot, user corrections, and what was half-done. But the **raw transcript is
still on disk**. This skill reads it and rebuilds your working context from it.

The mechanism is a bundled script. **You never read the raw JSONL yourself** — the original
session overflowed the window once already, and re-reading a multi-MB transcript just
re-overflows it. The script does the megabyte-scale parsing deterministically and hands you a
small structured capsule; you integrate that and keep working.

## When to use

- **Right after a compaction**, continuing prior work, when the summary feels thin or you
  notice you're about to redo something the session already did.
- The user invokes `/rehydrate`, or asks "what did we decide about X", "what was the last
  error", "what were we doing before the summary".

Skip it when: the session is fresh (no prior work, nothing was compacted); you want durable
cross-session facts (use **memory**) or task state (use **todo** / `TODO.md`); or you just
want to replay a session (`codex resume` / `grok --resume`).

## Workflow

The script auto-detects the harness from the environment and reads only that harness's store.
Run it from the project root (canonical path — works from any of the three harnesses):

```bash
REHYDRATE=~/dotfiles/agents/extensions/skills/rehydrate/scripts/rehydrate.py
```

1. **Broad pass (default).** Recover the orientation capsule:
   ```bash
   uv run "$REHYDRATE" digest --cwd "$PWD"
   ```
   Read the capsule into your working context. **Do not** show it to the user — it's for your
   own continuity. Then continue the original task.

2. **No compaction?** If it prints `NO_COMPACTION`, the session wasn't compacted and there's
   nothing to recover — stop, don't fabricate. If it prints `AMBIGUOUS` (several live sessions
   share this cwd), it refuses to guess — run `doctor` and pass the right `--harness`, or pick
   the session explicitly rather than risk recovering the wrong one's work.

3. **Targeted follow-up.** For a specific gap, query the raw pre-boundary records directly:
   ```bash
   uv run "$REHYDRATE" query --cwd "$PWD" --q "last error in the locator script"
   ```
   Each hit carries an `L<line>` anchor; if you need the full context of one, `Read` that line
   range of the transcript path the capsule printed — a surgical fetch, never the whole file.

4. **Debugging the locator.** `uv run "$REHYDRATE" doctor --cwd "$PWD"` shows which session was
   picked and why. Pass `--harness claude|codex|grok` if auto-detection is wrong.

## Guards

- **Recovered state is evidence, not current truth.** The transcript shows what *was* true at
  some past turn; files, branches, and decisions may have changed since (including after the
  compaction). Before acting on any recovered claim — especially "file X was edited to do Y" —
  re-check the live state (`git status`, re-`Read` the file). The capsule says this too.
- **Secrets** in the transcript are redacted to `[REDACTED:type]` before they reach you. If you
  see a redaction marker, don't try to recover the original.
- **The capsule is budget-capped** (~3–4k tokens by default; `--max-chars` to change). If a
  section says "+N more", that's the index — use `query` to fetch the specific item, don't try
  to dump everything.
- **Don't echo the capsule to the user.** Its visible effect should be that your *next* actions
  have continuity — not a status report.

## How it works (pointers)

Per-harness storage, encoding, and compaction-marker details — and the gotchas behind them —
live in `references/`. Read the relevant one only if the locator misbehaves or a harness
changed its format:

- `references/claude.md` — `~/.claude/projects/<enc>/<uuid>.jsonl`; `CLAUDE_CODE_SESSION_ID` /
  `<pid>.json` resolver; `compact_boundary` + `away_summary` + `isCompactSummary` markers;
  `isSidechain` filtering.
- `references/codex.md` — date-bucketed `rollout-*.jsonl`; `session_meta.cwd` match;
  `forked_from_id`; `type:"compacted"` / `replacement_history` (can be huge — streamed).
- `references/grok.md` — url-encoded cwd (+ `.cwd` fallback); `summary.json` `updated_at`;
  JSON-RPC records (`.params.update.sessionUpdate`); `signals.json.compactionCount`.
- `references/schema.md` — the normalized event model, extraction ranking, redaction, and the
  format-drift policy.

Compaction detection is **structural** (record type/subtype/flag), never a text search for the
word "compact" — that matches ordinary task text and is wrong almost every time.
