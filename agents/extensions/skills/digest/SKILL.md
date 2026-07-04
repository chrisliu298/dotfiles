---
name: digest
user-invocable: true
description: |
  Re-layer the previous response (or a named file) into a fast-to-skim form: answer first,
  a review-map or key-findings short version, action-changing blockers only, detail pulled
  on demand. Restructures for fast reading WITHOUT dropping substance.
  Use when a reply came out dense, or the user says "tl;dr", "too long", "wall of text",
  "make this skimmable", "digest that", or invokes "digest".
  Do NOT use to summarize-away detail, on already-short replies, or to clean code (use deslop).
allowed-tools: Read, Write
---

## What this does

Turn a dense answer into a fast-to-skim form the reader can absorb in seconds, with all detail kept and pulled on demand. This is restructuring, not summarizing: every decision, number, file path, command, caveat, risk, and citation in the source must survive. Write it in plain language, and make it stand alone.

## Target

Default: the immediately preceding assistant message. If the user names a file or path, `Read` it and use that instead. Emit only the re-layered version—no preamble, no commentary.

## Output shape

Re-emit in this order (mirrors the Response Contract in CLAUDE.md / AGENTS.md):

1. **Answer** — one line: the outcome, answer, or decision. Never buried.
2. **Short version** the reader can act on without scrolling:
   - Code / changes → a Markdown table with real `|`-delimited columns, one row per file: `| File | What changed | Why | Risk | How to check |` (never a single column with `·`-joined fields).
   - Research / analysis → the key findings as tight bullets, most-important first.
3. **Detail** — keep logs, long rationale, alternatives, and full citations below the short version; do not delete them. Add pull handles ("expand the X risk", "show the full diff"). If the detail runs past ~one screen, `Write` it to `~/.ai/reports/<timestamp>-<task-slug>.md` and leave only an index + path inline.

## Rules

- **Preserve substance.** Cut only filler: preamble, restating the request, hedging, narration ("I then searched…"), and redundant explanation. Never cut a decision, risk, path, command, number, or source.
- **Blockers, not doubt.** Carry a blocker inline in the answer or the short-version bullet it affects—a failed check, an answer-flipping assumption, or an irreversible action taken—and drop it when none is decision-relevant.
- **Cap the visible layer, not the content.** Answer ≤1 line; short version ≤~7 bullets or one row per unit. Don't compress the content into vagueness—a digest that hides needed detail fails as badly as the wall of text it replaced.
- **First screen complete.** The short version must be enough to act on, not a teaser that forces a re-read.
- **Terminal-safe layering.** Section order + scrollback, not `<details>` folding (it doesn't collapse in a plain terminal). Reserve `<details>`/HTML for browser- or GitHub-rendered output.
- **Compose, don't duplicate.** `digest` only restructures. For AI cadence run `humanizer`; for code-diff slop run `deslop`—each a separate pass.
