"""Batched local retrieval. Source parsers own redaction and transcript semantics.

One in-memory inverted index per invocation; the existing per-file cache remains
our only persistent state. Query variants come from the invoking agent.
"""
from __future__ import annotations

import importlib.util
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from file_cache import get_or_build


def backend(source):
    name = f"recall_backend_{source}"
    if name not in sys.modules:
        path = Path(__file__).resolve().parents[1] / source / "scripts" / "recall.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def load(source, cwd, query):
    api = backend(source)
    if source == "codex":
        root = api.session_root()
        inventory = api.file_inventory(root)
        turns, stats = api.load_turns(api.files_for_scope(inventory, "all", cwd=cwd, session_id=""))
        excluded = api.current_session_id()
        resolution = "session-id" if excluded else "unavailable"
        if excluded:
            turns = [turn for turn in turns if turn.session_id != excluded]
        rows = []
        for turn in turns:
            hit = api.turn_json(turn, root, 0)
            rows.append(dict(hit, session=turn.session_id, text=turn.text,
                             date=turn.timestamp[:10], order=turn.ordinal, cache_path=str(turn.path)))
        metadata = {"stats": stats.as_dict(), "current_task_exclusion": ("resolved" if resolution == "session-id" else
                                               "inferred" if excluded else "unresolved"),
                    "excluded_current_task": excluded or None}
    else:
        turns, stats = api.build_corpus(cwd, include_all=False, since_secs=0,
                                       max_files=0, exclude_session=api.current_session_id(), scope="all")
        rows = [dict(api.doc_json(turn, 0), text=turn.text, order=turn.line,
                     token_counts=dict(Counter(turn.tokens))) for turn in turns]
        metadata = {"stats": stats, "current_task_exclusion":
                    "resolved" if api.current_session_id() else "unresolved"}
    if source == "codex":
        by_file = defaultdict(list)
        for row in rows:
            by_file[row.pop("cache_path")].append(row)
        language = backend("claude")
        for path, messages in by_file.items():
            counts = get_or_build(Path(path), "codex-search-tokens", api.PARSER_VERSION + language.PARSER_VERSION, lambda: {
                r["locator"]["item_id"]: dict(Counter(language.tokenize(r["text"]))) for r in messages})
            for row in messages:
                row["token_counts"] = counts.get(row["locator"]["item_id"], {})
    return rows, metadata


def excerpt_start(text, terms):
    positions = [text.lower().find(term) for term in terms if term]
    positions = [pos for pos in positions if pos >= 0]
    return max(0, min(positions, default=0) - 100)


def excerpt(text, terms, cap=600):
    start = excerpt_start(text, terms)
    return ("…" if start else "") + text[start:start + cap] + ("…" if start + cap < len(text) else "")


def retrieve(rows, queries, limit=5, roles="both", since=None, until=None):
    """Return distinct sessions with separately anchored supporting messages.

    Windows of up to three messages connect a topic, options and a short answer.
    Role/date filters apply to each message before indexing. Fusion uses ranks,
    never raw scores across queries. No lexical hit is a verified decision.
    """
    language = backend("claude")
    selected = [r for r in rows if (roles == "both" or r["role"] == roles)
                and (not since or r["date"] >= since) and (not until or r["date"] <= until)]
    sessions = defaultdict(list)
    for row in rows:
        sessions[row["session"]].append(row)
    eligible = {id(row) for row in selected}
    units = []
    for messages in sessions.values():
        messages.sort(key=lambda r: (r.get("timestamp", r.get("date", "")), r["order"]))
        for i, row in enumerate(messages):
            if id(row) not in eligible:
                continue
            units.append([row])
            # Never bridge a filtered-out turn or a different session.
            for size in (2, 3):
                window = messages[max(0, i - size + 1):i + 1]
                if len(window) == size and all(id(item) in eligible for item in window):
                    units.append(window)
    normalized = [language.normalize_query(q) for q in queries]
    query_terms = {term for _, terms, _ in normalized for term in terms}
    postings = defaultdict(list)
    lengths = []
    token_cache = {}
    for i, unit in enumerate(units):
        counts = Counter()
        for row in unit:
            key = id(row)
            if key not in token_cache:
                token_cache[key] = Counter(row["token_counts"]) if "token_counts" in row else Counter(language.tokenize(row["text"]))
            counts.update(token_cache[key])
        lengths.append(sum(counts.values()))
        for term in query_terms & counts.keys():
            postings[term].append((i, counts[term]))
    average = sum(lengths) / max(1, len(lengths)) or 1
    fused = {}
    attempts = []
    for query_index, query in enumerate(queries):
        cleaned, terms, groups = normalized[query_index]
        scores, matched = defaultdict(float), defaultdict(set)
        for term in terms:
            hits = postings.get(term, [])
            weight = math.log(1 + (len(units) - len(hits) + .5) / (len(hits) + .5))
            for i, count in hits:
                scores[i] += weight * count * 2.5 / (count + 1.5 * (.25 + .75 * lengths[i] / average))
                matched[i].add(term)
        ranked = []
        for i, score in scores.items():
            coverage = sum(bool(group & matched[i]) for group in groups) / max(1, len(groups))
            if coverage < .6:
                continue
            unit = units[i]
            # A window must contribute evidence beyond a single message.
            if len(unit) > 1 and any(matched[i] <= token_cache[id(row)].keys() for row in unit):
                continue
            ranked.append((score * coverage * (1.4 if any(r["role"] == "user" for r in unit) else 1), i, coverage))
        ranked.sort(key=lambda hit: (-hit[0], -hit[2], hit[1]))
        seen = set()
        for score, i, coverage in ranked:
            unit = units[i]
            session = unit[0]["session"]
            if session in seen:
                continue
            seen.add(session)
            rank = len(seen)
            entry = fused.setdefault(session, {"session": session, "fusion_score": 0,
                                               "matched_queries": [], "evidence": []})
            entry["fusion_score"] += coverage ** 2 / (60 + rank)
            entry["matched_queries"].append(query_index + 1)
            for row in unit:
                anchor = row.get("locator", {}).get("item_id", row.get("line"))
                if any(e["anchor_key"] == anchor for e in entry["evidence"]):
                    continue
                hit = {key: value for key, value in row.items() if key not in ("text", "order", "score", "coverage", "token_counts")}
                hit.update(anchor_key=anchor, excerpt=excerpt(row["text"], terms),
                           query_index=query_index + 1, excerpt_offset=excerpt_start(row["text"], terms),
                           coverage=round(coverage, 3))
                entry["evidence"].append(hit)
        attempts.append({"query": language.redact(query), "matching_sessions": len(seen),
                         "searchable_terms": len(groups)})
    ordered = sorted(fused.values(), key=lambda e: (-e["fusion_score"], e["session"]))[:limit]
    candidates = []
    for rank, session in enumerate(ordered, 1):
        evidence = session["evidence"][:6]
        candidate = dict(evidence[0])
        candidate.update(rank=rank, fusion_score=round(session["fusion_score"], 6),
                         matched_queries=session["matched_queries"], evidence=evidence)
        candidates.append(candidate)
    return {"status": "ambiguous" if candidates else
            "empty_query" if not any(a["searchable_terms"] for a in attempts) else "no_match",
            "candidates": candidates, "queries": attempts,
            "coverage": {"messages_available": len(rows), "messages_searched": len(selected),
                         "sessions_searched": len({r["session"] for r in selected}),
                         "roles": roles, "since": since, "until": until},
            "verification_required": True}


def search(source, queries, cwd, limit, roles, since=None, until=None):
    started = time.monotonic()
    rows, metadata = load(source, cwd, queries[0])
    result = retrieve(rows, queries, limit, roles, since, until)
    result.update(metadata, elapsed_ms=round((time.monotonic() - started) * 1000))
    return result


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("codex", "claude"), required=True)
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--roles", default="both")
    parser.add_argument("--since")
    parser.add_argument("--until")
    args = parser.parse_args()
    try:
        output = search(args.source, args.query, args.cwd, args.limit, args.roles, args.since, args.until)
    except Exception as exc:
        output = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(output, ensure_ascii=False))
