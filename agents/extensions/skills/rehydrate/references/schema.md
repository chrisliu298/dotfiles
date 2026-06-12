# Normalized model, extraction, redaction, drift policy

This is the harness-agnostic half. Adapters (`claude.md`/`codex.md`/`grok.md`) know storage and
record shapes; everything here is shared. **Adapters know storage; the digest builder knows
continuity semantics — keep them separate.**

## Normalized event

Each adapter's `events()` yields a uniform `Event`:

```
line, role(user|assistant|tool|system), kind(user_message|assistant_message|file_op|command|
command_output), text(truncated+later redacted), paths[], command, exit_code, sidechain
```

Only events **before the compaction boundary** are scanned (that's the detail the summary
dropped). Sidechains are excluded from the broad pass by default.

## Extraction ranking (what the capsule keeps)

High value, in priority order — the things compaction reliably loses and that are expensive to
re-derive:

1. **User directives & corrections** — highest signal/byte, latest wins. Matched on cues like
   `no,` / `actually` / `instead` / `don't` / `use X not Y` / `revert`.
2. **Decisions & ruled-out approaches** — assistant cues `decided`/`chose`/`because`/`ruled out`/
   `won't work`/`reverted`. Ruled-out is its own high-value class (stops repeated dead-ends).
3. **Files touched** — dedup by path, latest op wins. Flagged "verify against disk".
4. **Commands & errors** — failures kept with the error signature; successes as cmd+exit.
5. **Open threads** — the most recent user turns before the boundary.

Dropped as noise: verbose/successful tool output bodies, redundant re-reads, reasoning/thinking
blobs, token-count and permission/mode bookkeeping, skill/command listings, base64/images,
sidechain branches.

## Condensation contract

- The **script** is the filter; the **model** is the integrator. The model never reads raw JSONL.
- **Index-and-fetch, not re-summarize.** The broad `digest` is the index (with `L<line>`
  anchors); `query` fetches specifics; a deep gap is a surgical `Read` of a line range. Avoid
  model map-reduce over the transcript — it re-summarizes the thing the summary already lossily
  summarized, and risks re-overflow.
- **Budget in characters**, not tokens (the script can't know the harness model's tokenizer).
  Default ~14000 chars ≈ 3–4k tokens; hard-truncate with a "use query" pointer at the cap.

## Cross-session survey (`survey`)

`digest` recovers the current session *below its compaction boundary*; `survey` orients on recent
**other** sessions in the same cwd. Same machinery, inverted relationship to multiplicity (it's the
input, not an `AMBIGUOUS` error) and to scope (boundary-less recent **tail**, not pre-boundary body):

- **Selection** reuses the adapter enumerator (Claude `candidates()`), newest-first, dropping the
  current session, anything older than `--since` (default 24h), and **non-interactive** sessions —
  see `claude.md` for the interactive predicate. `survey` is **Claude-only**: the
  "user-spawned interactive vs relay/headless/subagent" signal is Claude-specific; other adapters
  have no `interactive_siblings()` and `cmd_survey` returns `SURVEY_UNSUPPORTED`.
- **Re-overflow** is contained by reading only a bounded **tail** per sibling (`tail_events()` keeps
  a `deque(maxlen=SURVEY_TAIL_EVENTS)` while streaming `events(path, None)`), then ranking it with
  the shared `collect_buckets()` at a **per-session sub-budget** (`max_chars // N`, floor 2000). The
  model still never reads raw JSONL; the aggregate stays inside the same `--max-chars` cap.
- **Capsule** is per-session sections (provenance + relative age on each — no merged timeline, which
  would manufacture false causality between unrelated windows) plus a cross-session **files-touched**
  rollup (latest op wins). Guards add: siblings may be unrelated parallel work; don't present a
  sibling's state as current truth. `collect_buckets()` / `_budget_lines()` are shared with
  `build_capsule()` so the ranking never forks.

## Redaction

Applied to every emitted snippet before output: OpenAI/xAI/GitHub/AWS keys, `Bearer` tokens,
JWTs, PEM private-key headers, and `*_API_KEY=`/`*_SECRET=`/`*_TOKEN=`/`*_PASSWORD=` assignments →
`[REDACTED:<type>]`, with a trailing count. Never the raw value. The script only ever reads the
stores; redaction is output-side.

## Failure / drift policy

- **No compaction** → exit `NO_COMPACTION` (13); never fabricate recovery.
- **Ambiguous current session** (≥2 cwd-matches within seconds) → exit `AMBIGUOUS` (12) with a
  candidate list; don't guess the wrong session's work.
- **Format drift** — adapters use tolerant `.get()` access and structural type checks. A startup
  `format_ok` probe (each adapter's `recognizes()`) scans the first ~200 records and adds a
  **warning** to the capsule when none are recognized — i.e. a wholesale record-type rename is
  loud, not silent. A renamed *boundary* marker (records still recognized) still surfaces as
  `NO_COMPACTION`, but the message hints at drift and points here. On drift, update the markers in
  `claude.md`/`codex.md`/`grok.md` and the small per-adapter detectors in `rehydrate.py`, then
  re-stamp the "Verified YYYY-MM-DD / version" line.

## Status: not yet exercised against a real compaction (Codex/Grok)

Record *shapes* are verified, but on 2026-06-10 the freshly-sampled Claude and Grok sessions on
this machine had **no** compaction, and only an older Codex rollout had a real `compacted`
record. Boundary detection for Codex/Grok is therefore spec-correct but not end-to-end tested.
The first real post-compaction run in each harness is the validation — if `digest` returns
`NO_COMPACTION` when you *know* the session was compacted, run `doctor` and check the marker
shapes here against the live file.
