# Normalized model, ranking, redaction, drift policy

The retrieval half of recall. `claude.md` covers storage and record shapes; everything here is the
search pipeline: how a transcript becomes searchable Docs, how they're ranked, and how the
confidence gates decide silent-load vs ask vs no-match.

## Normalized event → Doc

`events()` yields a uniform `Event` per turn:

```
line, role(user|assistant|tool), kind(user_message|assistant_message|file_op|command|command_output),
text(truncated+redacted), ts, sidechain
```

`build_corpus()` keeps only **user/assistant text events** (sidechains, tool output, and injected
turns dropped — see `claude.md`), and wraps each in a `Doc`: `session, transcript, line, role, text,
date, tokens, session_rank`. The unit of retrieval is the **individual turn**, because that's what
carries an `L<line>` anchor and what the agent loads. Surrounding context is fetched on demand with
`show`, never by indexing windows.

## Ranking — BM25 + boosts (stdlib, no embeddings)

Tokenization is identifier-aware: a token is kept whole **and** sub-split on camelCase / snake_case /
kebab / dotted paths, so `authRetry` / `auth_retry` / `auth-retry` all reach `auth` + `retry`.
Stopwords (incl. recall-boilerplate words) and <2-char tokens are dropped. The query is normalized
first — trigger phrases ("what did we decide about", "remember when") stripped — then tokenized from
the **original** so an identifier embedded in boilerplate survives.

Score per Doc = `BM25(k1=1.5, b=0.75)` over matched query terms, times multiplicative boosts:

- **user role ×1.6** — "what did *we* decide" usually wants what the user said.
- **decision/correction cue ×1.25** — the turn contains `decided`/`chose`/`because`/`instead`/
  `don't`/`prefer`/`cap`/`revert`/`agreed`… (the cue regex).
- **verbatim phrase ×1.4** — the normalized query appears as a substring.
- **recency** — newest scanned session +15%, oldest +0% (linear by scan rank). Mild: an older
  explicit decision still beats a recent passing mention.

Why lexical, not embeddings: it stays stdlib-only (the `uv` inline-script zero-dep bar), and its
failure mode is a **clean miss → ask the user**, not a confident semantically-plausible wrong match.
The agent itself supplies the "semantic" layer — it expands query terms before the call and can
re-rank the returned top-k.

## Confidence gates (the safety surface)

`search` returns one of three statuses; the agent branches on it:

- **`confident`** (exit 0) — top score ≥ `MIN_SCORE` (0.8), covers ≥half the query terms, **and**
  beats #2 by ≥`CONFIDENT_MARGIN` (1.25×). Safe to silently load the top hit.
- **`ambiguous`** (exit 11) — matches exist but no clear winner (tight top-1/top-2 band). The agent
  shows 2–3 candidates and asks; it must **not** silent-pick.
- **`no_match`** (exit 13) — nothing cleared the floor (or no content terms after boilerplate strip).
  The agent escalates once (`--max-files 0`, every past session) then says so — **never fabricates**.

These gates, plus the one-line confirmation, are what carry the highest design risk: silently acting
on a wrong match. A wider scan (`--max-files 0`) or `--all` (include relay/headless) is the recovery
lever when the default recency window misses.

## Latency & scope

Retrieval is **stateless** — every `search` re-scans transcripts; there is no persistent index.
Justification: the searchable user/assistant text is a thin sliver of the on-disk bytes, but parsing
is still CPU-bound, so the cost scales with **files scanned** (~2.5s at the default 150-file recency
window; ~9s for the full ~530-interactive-file corpus on this machine). The default window covers the
dominant "as I mentioned earlier" case fast; the agent escalates to a full scan only on a miss. If a
measured window scan ever climbs past a few seconds, a persistent `(path, mtime, size)`-keyed sqlite
index (stdlib `sqlite3`, redacted at write time) is the documented tier-2 escape hatch — deferred
until a real latency number justifies its invalidation/concurrency/secrets-at-rest cost.

## Redaction

Applied to every emitted snippet before output (the single `clip()` choke point): OpenAI/xAI/GitHub/
AWS keys, `Bearer` tokens, JWTs, PEM private-key headers, and `*_API_KEY=`/`*_SECRET=`/`*_TOKEN=`/
`*_PASSWORD=`/`*_PLAN_KEY=` assignments → `[REDACTED:<type>]`, with a trailing count. Never the raw
value. The script only ever reads the stores; redaction is output-side. (If a persistent index is
ever added, redact at write time so secrets never persist to disk.)

## Failure / drift policy

- **No match** → `no_match` (13); never fabricate a recalled decision.
- **Tolerant parsing** — `events()` uses `.get()` access and structural type checks; a vanished or
  locked transcript is skipped, a multi-MB record is peeked-and-drained (never fully parsed), and a
  malformed line is skipped. A wholesale record-type rename (Claude Code changes its JSONL shapes)
  would show up as steadily empty results — re-check the shapes in `claude.md` against a live file,
  update `events()` / the `TUI_TYPES` set / the injected-prefix list, and re-stamp the "Verified
  YYYY-MM-DD / version" line in `claude.md`.
