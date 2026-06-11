---
name: digest
user-invocable: true
description: |
  Re-layer the previous response (or a target file) into a skim-first review surface per the
  Response Contract: verdict first, a review-map or key-findings skim layer, uncertainty
  surfaced, detail pulled on demand. Restructures for human reading WITHOUT dropping substance.
  Use when a reply came out dense, or the user says "tl;dr", "too long", "wall of text",
  "make this skimmable", "digest that", or invokes "digest".
  Do NOT use to summarize-away detail, on already-short replies, or to clean code (use deslop).
allowed-tools: Read, Write
---

## What this does

Transform a dense answer into a **skim-first review surface** the reader can absorb in seconds, with all detail preserved and pulled on demand. This is *restructuring, not summarizing*: every decision, number, file path, command, caveat, risk, and citation in the source must survive.

## Target

By default, operate on the **immediately preceding assistant message**. If the user names a file or path, `Read` it and operate on that instead. Emit only the re-layered version—no preamble, no meta-commentary.

## Output shape

Re-emit the content in this order (mirrors the Response Contract in CLAUDE.md / AGENTS.md):

1. **Verdict** — one line: the outcome, answer, or decision. Never buried.
2. **Skim layer** the reader can act on without scrolling:
   - Code / changes → a review-map table: `file · what changed · why · risk · how to check`.
   - Research / analysis → the key findings as tight bullets, most-important first.
3. **Not done / not checked** — skipped checks, assumptions, the least-verified claim. Add a **context dividend** when relevant: the few things learned that the reader didn't see ("observed X → changed Y").
4. **Detail** — keep logs, long rationale, alternatives, and full citations below the skim layer; do not delete them. Offer explicit pull handles ("expand the X risk", "show the full diff"). If the detail would exceed ~one screen, `Write` it to `~/.ai/reports/<timestamp>-<task-slug>.md` and leave only the index + path inline.

## Rules

- **Preserve substance.** Cut only filler: preamble, restating the request, hedging, narration ("I then searched…"), and redundant explanation. Never cut a decision, risk, path, command, number, or source.
- **Cap shape, not reasoning.** Bound the visible layer (verdict ≤1 line; skim ≤~7 bullets, or a table row per file/unit); don't compress the underlying content into vagueness. A digest that hides needed detail fails as badly as the wall of text it replaced.
- **First screen complete.** The skim layer must be enough to act on—not a teaser that forces a re-read.
- **Terminal-safe layering.** Use section order + scrollback, not `<details>` folding (it does not collapse in a plain terminal). Reserve `<details>`/HTML for browser- or GitHub-rendered output.
- **Compose, don't duplicate.** For AI cadence run the `humanizer` skill as a separate pass; for code-diff slop run `deslop`. `digest` only restructures.
