#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Gold-set eval for the production retrieval path (shared/retrieve.py), Claude and Codex stores.

Each source corpus is loaded once through retrieve.load, then every gold item runs through
retrieve.retrieve, the function `global_recall.py search` uses. Two gold kinds:

  - episodes (--episodes, default ~/.local/state/recall-eval/episodes.jsonl): descriptive recall
    ("那次我们…"). Measures whether the right SESSION ranks (session@1/5/20) and whether a top-k
    evidence message holds the episode's conclusion. Host-local, never committed: the labels quote
    private conversations. One JSON object per line (# = comment):
      {"id", "source": "claude|codex", "query": the user's description (avoid the session title's
       wording), "variants": phrasings written by an agent that saw only the description,
       "sessions": accepted session-id prefixes, "expect": answer-distinct conclusion keywords,
       "note"}
  - ../../claude/eval/gold.jsonl positives: fact-shaped recall, scored by evidence keywords only,
    as a regression check for the existing behavior.

Query sets: `raw` sends only the user's description; `variants` sends the description plus the
agent-written phrasings stored in the gold file (what SKILL.md step 2 asks the agent to do).
It measures, never tunes. Environment-specific: meaningful only on the machine with this history.

  uv run agents/skills/recall/shared/eval/run_eval.py -v
"""
import argparse
import importlib.util
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EPISODES = Path.home() / ".local" / "state" / "recall-eval" / "episodes.jsonl"
FACTS = HERE.parents[1] / "claude" / "eval" / "gold.jsonl"
KS = (1, 5, 20)


def load_retrieve():
    spec = importlib.util.spec_from_file_location("retrieve", HERE.parent / "retrieve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_gold(path):
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def anchor(row):
    return row.get("locator", {}).get("item_id", row.get("line"))


def run(r, source, cwd, queries, limit):
    """retrieve() on index-backed rows for these queries, plus an anchor -> row map for scoring."""
    rows, _ = r.load(source, cwd, queries)
    return r.retrieve(rows, queries, limit=limit), {(row["session"], anchor(row)): row for row in rows}


def score(result, rows_by_anchor, item, k_evidence):
    """(session rank or None, evidence rank or None): first candidate in the gold session set, and
    first candidate whose evidence text contains an expect keyword."""
    sessions = item.get("sessions", [])
    expect = [k.lower() for k in item.get("expect", [])]
    session_rank = evidence_rank = match = None
    for rank, candidate in enumerate(result["candidates"], 1):
        if session_rank is None and any(candidate["session"].startswith(s) for s in sessions):
            session_rank, match = rank, candidate.get("match")
        if evidence_rank is None and expect and rank <= k_evidence:
            texts = (r_text(rows_by_anchor.get((candidate["session"], e["anchor_key"])))
                     for e in candidate["evidence"])
            if any(any(k in text.lower() for k in expect) for text in texts):
                evidence_rank = rank
    return session_rank, evidence_rank, match


def r_text(row):
    return row["text"] if row and "text" in row else row["fetch"]() if row else ""


def pct(hits, total):
    return f"{100 * hits / total:3.0f}% ({hits}/{total})" if total else "n/a"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cwd", default=str(Path.cwd()))
    parser.add_argument("--episodes", type=Path, default=EPISODES, help="host-local episode gold file")
    parser.add_argument("--queries", choices=("raw", "variants", "both"), default="both")
    parser.add_argument("--evidence-k", type=int, default=5, help="candidates checked for the conclusion")
    parser.add_argument("-v", "--verbose", action="store_true", help="per-item ranks")
    args = parser.parse_args()

    os.environ.setdefault("RECALL_CACHE_DIR", str(Path.home() / ".cache" / "recall"))  # as global_recall
    r = load_retrieve()
    episodes = read_gold(args.episodes)
    facts = [dict(item, source="claude") for item in read_gold(FACTS) if not item.get("negative")]
    present = {}
    for source in sorted({item["source"] for item in episodes + facts}):
        started = time.monotonic()
        rows, _ = r.load(source, args.cwd, [])          # refreshes the index; no terms needed
        present[source] = {row["session"] for row in rows}
        print(f"corpus {source}: {len(rows)} messages, {len(present[source])} sessions "
              f"({time.monotonic() - started:.1f}s)")

    query_sets = ("raw", "variants") if args.queries == "both" else (args.queries,)
    for query_set in query_sets:
        print(f"\n## queries={query_set}")
        rows_out, session_hits, evidence_hits, absent = [], {k: 0 for k in KS}, 0, []
        for item in episodes:
            if not any(s.startswith(p) for p in item["sessions"] for s in present[item["source"]]):
                absent.append(item["id"])
                continue
            queries = [item["query"]] + (item.get("variants", []) if query_set == "variants" else [])
            result, by_anchor = run(r, item["source"], args.cwd, queries, max(KS))
            session_rank, evidence_rank, match = score(result, by_anchor, item, args.evidence_k)
            for k in KS:
                session_hits[k] += session_rank is not None and session_rank <= k
            evidence_hits += evidence_rank is not None
            rows_out.append((item["id"], item["source"], session_rank, evidence_rank, match))
        n = len(rows_out)
        print(f"episodes scored: {n}" + (f"  (gold session not in corpus: {', '.join(absent)})" if absent else ""))
        for k in KS:
            print(f"  session@{k:<2}            : {pct(session_hits[k], n)}")
        print(f"  conclusion@{args.evidence_k} evidence  : {pct(evidence_hits, n)}")
        if args.verbose:
            for fid, source, session_rank, evidence_rank, match in rows_out:
                print(f"    {fid:<20} {source:<6} session={session_rank or '-':<3} "
                      f"conclusion={evidence_rank or '-':<3} via={match or '-'}")

        if query_set == "raw":   # fact gold has no variants; it is the regression check
            fact_hits = 0
            for item in facts:
                result, by_anchor = run(r, "claude", args.cwd, [item["query"]], args.evidence_k)
                _, evidence_rank, _ = score(result, by_anchor, item, args.evidence_k)
                fact_hits += evidence_rank is not None
            print(f"facts (claude gold.jsonl) answer@{args.evidence_k}: {pct(fact_hits, len(facts))}")


if __name__ == "__main__":
    main()
