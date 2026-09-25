# Normalized model, ranking, redaction, drift policy

The retrieval half of recall. `transcript-store.md` covers storage and record shapes; everything here is the
search pipeline: how a transcript becomes searchable Docs, how they're ranked, and how the
confidence gates decide silent-load vs ask vs no-match.

## Normalized event → Doc

`events()` yields a uniform `Event` per turn:

```
line, role(user|assistant|tool), kind(user_message|assistant_message|file_op|command|command_output),
text(truncated+redacted), ts, sidechain
```

`build_corpus()` keeps only **user/assistant text events** (sidechains, tool output, and injected
turns dropped — see `transcript-store.md`), and wraps each in a `Doc`: `session, transcript, line, role, text,
date, tokens, session_rank`. The unit of retrieval is the **individual turn**, because that's what
carries an `L<line>` anchor and what the agent loads. Surrounding context is fetched on demand with
`show`, never by indexing windows.

## Ranking — BM25 + boosts (stdlib, no embeddings)

Tokenization is identifier-aware: a token is kept whole **and** sub-split on camelCase / snake_case /
kebab / dotted paths, so `authRetry` / `auth_retry` / `auth-retry` all reach `auth` + `retry`.
CJK runs (no spaces) yield their characters, adjacent bigrams, and the whole run if short.
Stopwords (incl. recall-boilerplate words) and <2-char Latin tokens are dropped. The query is
normalized first — trigger phrases ("what did we decide about", "remember when") stripped — then
tokenized from the cleaned text. It is also split into **concept groups**, one per query word (a
compound identifier's whole form + sub-parts form one group; a CJK run gives one group per bigram).
Coverage and matched-count are measured in groups, so `claude-in-chrome` counts as one concept, not
three.

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

The gates key on **matched-term count + query coverage**, NOT raw score: BM25 scores are
unnormalized (they run ~10-40 on a real corpus), so a score floor is useless — `eval/gold.jsonl`
showed nonsense queries clearing any fixed floor while a multi-concept hit's *coverage* cleanly
separated signal from noise. Before the top is picked, **incidental** hits (a multi-concept query
matched by <2 concepts or <`CAND_MIN_COVERAGE` of them) are dropped, so a high-scoring one-word
overlap can't mask the real multi-concept statement ranked below it. Thresholds
(`CAND_MIN_COVERAGE` 0.6, `CONFIDENT_COVERAGE` 0.6, `CONFIDENT_MARGIN` 1.15) are calibrated against
that gold-set (the 2026-09-25 numbers are in the comment above them in `recall.py`). `search`
returns one of four statuses; the agent branches on it:

- **`confident`** (exit 0) — a multi-term query, top covers ≥60% of the terms, leads the best
  *distinct* runner-up by ≥1.15×, and the top is a **user statement** (an assistant-role top, or a
  user turn that ends in `?` without a decision cue — `kind: question` — is capped to ambiguous).
  Safe to load and answer with the provenance line.
- **`ambiguous`** (exit 11) — a real candidate but not clearly the answer (a 1-term query, an
  assistant-role top, or coverage/lead below the confident bar). The agent shows 2–3 candidates and
  asks; it must **not** silent-pick.
- **`empty_query`** (exit 12) — no content terms left after the boilerplate strip. The agent retries
  with concrete names/values/identifiers.
- **`no_match`** (exit 13) — nothing covered the query (no hit, or only incidental overlap). The
  output carries an `escalate` hint (`--max-files 0` → `--scope all` → `--scope all --max-files 0`);
  the agent widens, then says so — **never fabricates**.

The top-level `confirmation` (`recall: <YYYY-MM-DD> · <session prefix> · <gist>`, the format shared
with the Codex build) is emitted only for `confident`; every candidate carries its own so the agent
can print the one it (or the user) chose.

These gates, plus the one-line confirmation, carry the highest design risk: silently acting on a
wrong match. The margin is only a weak tiebreak (at corpus scale there is almost always a
near-scoring runner-up), so coverage + the user-turn requirement do the real gating. Re-run
`eval/run_eval.py` after any threshold change — it fails closed on a single false-confident.

## Latency & scope

`--scope project` (default) scans `<projects>/<encoded cwd>/`; `--scope all` scans every project dir
in one global mtime order, so the same recency window spans projects, and each hit reports the
`project` (the record's own `cwd`) it came from. `show` looks in this project first, then all.
Each run ranks one corpus; BM25 scores are never compared across runs/scopes — widening happens only
on `no_match`, and the narrower scope's hit is preferred.

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
AWS/Google/Slack keys, `Bearer` tokens (any case), JWTs, PEM private keys, `*_API_KEY=`/`*_SECRET=`/
`*_TOKEN=`/`*_PASSWORD=`/`*_PLAN_KEY=` assignments (quoted JSON-style too), base64 `data:` URLs, and
500+-char opaque blobs → `[REDACTED:<type>]`, with a trailing count. A PEM `BEGIN … PRIVATE KEY`
with no END line is redacted to the end of the turn. This is **best-effort** pattern matching — a
secret in an unrecognized shape passes through. The pattern set matches the
Codex build's. Never the raw
value. The script only ever reads the stores; redaction is output-side. (If a persistent index is
ever added, redact at write time so secrets never persist to disk.)

## Failure / drift policy

- **No match** → `no_match` (13); never fabricate a recalled decision.
- **Tolerant parsing** — `events()` uses `.get()` access and structural type checks; a vanished or
  locked transcript is skipped, a multi-MB record is peeked-and-drained (never fully parsed), and a
  malformed line is skipped. A wholesale record-type rename (Claude Code changes its JSONL shapes)
  would show up as steadily empty results — re-check the shapes in `transcript-store.md` against a live file,
  update `events()` / the `TUI_TYPES` set / the injected-prefix list, and re-stamp the "Verified
  YYYY-MM-DD / version" line in `transcript-store.md`.
