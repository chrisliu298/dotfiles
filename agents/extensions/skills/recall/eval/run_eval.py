#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""run_eval.py — gold-set eval for recall's retrieval + confidence gates.

Builds the project corpus ONCE (full interactive scan), runs each gold query through recall's own
`run_query` (the exact production path), and reports the metrics that decide whether the hand-tuned
thresholds (MIN_SCORE, the top/2nd margin, the coverage gate, the boost weights, the recency window)
are trustworthy:

  - recall@1 / recall@k   — does the right past statement surface, and at the top?
  - confident-precision   — WHEN status is `confident`, is the loaded (rank-1) hit actually correct?
  - FALSE-CONFIDENT       — a `confident` result that is wrong, or `confident` on a should-miss query.
                            This is the dangerous case the gates exist to prevent; ANY of these
                            exits the eval nonzero so it works as a regression gate.

A hit "is correct" iff its indexed text contains one of the gold item's answer-distinct `expect`
keywords (which are deliberately not the query terms). Run from anywhere:

  uv run agents/extensions/skills/recall/eval/run_eval.py --cwd /Users/you/dotfiles
  uv run .../eval/run_eval.py --all -v        # include relay/headless sessions; per-query table

Environment-specific: it reads ~/.claude/projects/<this cwd>, so it only means anything on a machine
that holds this project's session history. It does not retune anything — it MEASURES, so a threshold
change can be judged against a number instead of vibes.
"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECALL_PY = HERE.parent / "scripts" / "recall.py"


def load_recall():
    spec = importlib.util.spec_from_file_location("recall", RECALL_PY)
    m = importlib.util.module_from_spec(spec)
    sys.modules["recall"] = m            # register so dataclass introspection works (3.14)
    spec.loader.exec_module(m)
    return m


def hit_matches(text, expect):
    t = text.lower()
    return any(k.lower() in t for k in expect)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", default=str(Path.cwd()))
    ap.add_argument("--gold", default=str(HERE / "gold.jsonl"))
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--all", action="store_true", help="include relay/headless sessions too")
    ap.add_argument("-v", "--verbose", action="store_true", help="per-query table")
    args = ap.parse_args()

    m = load_recall()
    gold = [json.loads(ln) for ln in open(args.gold)
            if ln.strip() and not ln.lstrip().startswith("#")]

    t0 = time.time()
    exclude = m.current_session_id()
    docs, stats = m.build_corpus(args.cwd, include_all=args.all, exclude_session=exclude,
                                 since_secs=0, max_files=0)   # full scan = the quality denominator
    build_s = time.time() - t0

    rows, false_confident = [], []
    pos = neg = 0
    found1 = foundk = 0
    conf_total = conf_correct = 0
    status_counts = {"confident": 0, "ambiguous": 0, "no_match": 0}

    for g in gold:
        negative = g.get("negative", False)
        status, hits, terms = m.run_query(docs, g["query"], args.k)
        status_counts[status] = status_counts.get(status, 0) + 1
        rank = None
        if not negative:
            pos += 1
            for i, d in enumerate(hits):
                if hit_matches(d.text, g["expect"]):
                    rank = i + 1
                    break
            if rank == 1:
                found1 += 1
            if rank is not None:
                foundk += 1
        else:
            neg += 1

        if status == "confident":
            if negative:
                false_confident.append((g["id"], "confident on a should-miss query"))
            else:
                conf_total += 1
                if rank == 1:
                    conf_correct += 1
                else:
                    where = f"correct@{rank}" if rank else "correct not in top-k"
                    false_confident.append((g["id"], f"confident but rank-1 wrong ({where})"))
        rows.append((g["id"], "NEG" if negative else "POS", status, rank))

    def pct(n, d):
        return f"{100*n/d:.0f}% ({n}/{d})" if d else "n/a"

    print(f"# recall eval — {len(gold)} queries ({pos} positive, {neg} negative)")
    print(f"corpus: {stats['files_scanned']} interactive files, {stats['docs']} docs "
          f"(built in {build_s:.1f}s){' [--all]' if args.all else ''}")
    print(f"status: confident={status_counts['confident']} ambiguous={status_counts['ambiguous']} "
          f"no_match={status_counts['no_match']}")
    print()
    print(f"recall@1 (positives)        : {pct(found1, pos)}")
    print(f"recall@{args.k} (positives)        : {pct(foundk, pos)}")
    print(f"confident-precision         : {pct(conf_correct, conf_total)}  "
          f"(of confident results, rank-1 correct)")
    neg_clean = sum(1 for r in rows if r[1] == 'NEG' and r[2] == 'no_match')
    print(f"negatives → no_match        : {pct(neg_clean, neg)}")
    print(f"FALSE-CONFIDENT (must be 0) : {len(false_confident)}")
    for fid, why in false_confident:
        print(f"    ✗ {fid}: {why}")

    if args.verbose:
        print("\nid                     kind  status      correct-rank")
        for fid, kind, status, rank in rows:
            print(f"  {fid:<22} {kind}   {status:<11} {rank if rank else '-'}")

    # Gate: any false-confident (the dangerous case) fails the eval.
    sys.exit(1 if false_confident else 0)


if __name__ == "__main__":
    main()
