"""Batched local retrieval. Source parsers own redaction and transcript semantics.

Rows come from a persistent incremental index (index.py) holding only the query's terms;
scoring materializes only windows that contain one. Query variants come from the invoking agent.
"""
from __future__ import annotations

import importlib.util
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index import Index


def backend(source):
    name = f"recall_backend_{source}"
    if name not in sys.modules:
        path = Path(__file__).resolve().parents[1] / source / "scripts" / "recall.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def load(source, cwd, queries):
    """Index-backed rows for `queries`: refresh the source's index, then read only their terms."""
    language = backend("claude")
    terms = {term for query in queries for term in language.normalize_query(query)[1]}
    return Index(source, backend).rows(cwd, terms, backend(source).current_session_id() or None)


def excerpt_start(text, terms):
    positions = [text.lower().find(term) for term in terms if term]
    positions = [pos for pos in positions if pos >= 0]
    return max(0, min(positions, default=0) - 100)


def excerpt(text, terms, cap=600):
    start = excerpt_start(text, terms)
    return ("…" if start else "") + text[start:start + cap] + ("…" if start + cap < len(text) else "")


def text_of(row):
    """Message text; index-backed rows fetch it only when evidence is rendered."""
    return row["text"] if "text" in row else row["fetch"]()


def session_fill(selected, normalized, hot, length, exclude, limit):
    """Rank whole sessions for a description whose words are spread across one conversation.

    A session is one BM25 document (its messages plus a title bonus); a description that no
    single window covers can still land here. These rank after every message match, so they
    only fill a short list and never reorder message evidence.
    """
    by_session = defaultdict(list)
    for row in selected:
        by_session[row["session"]].append(row)
    counts, sizes, titles = {}, {}, {}
    language = backend("claude")
    for session, messages in by_session.items():
        total = Counter()
        for row in messages:
            total.update(hot.get(id(row), {}))
        counts[session] = total
        sizes[session] = sum(length[id(row)] for row in messages)
        titles[session] = set(language.tokenize(next((r["title"] for r in messages if r.get("title")), "")))
    if not counts:
        return []
    average = sum(sizes.values()) / len(counts) or 1
    fused = {}
    for query_index, (_, terms, groups) in enumerate(normalized):
        frequency = Counter(t for s in counts for t in set(terms) & (counts[s].keys() | titles[s]))
        idf = {t: math.log(1 + (len(counts) - n + .5) / (n + .5)) for t, n in frequency.items()}
        scores = {}
        for session, total in counts.items():
            if session in exclude:
                continue
            matched = {t for t in idf if total[t] or t in titles[session]}
            if not matched:
                continue
            # Conversational CJK splits into many cross-word bigrams, so a natural description can
            # never reach the window's 60%; ask for 30% of concepts, but at least two of them.
            hits = sum(bool(g & matched) for g in groups)
            if hits < max(min(2, len(groups)), math.ceil(.3 * len(groups))):
                continue
            coverage = hits / max(1, len(groups))
            score = sum(idf[t] * (total[t] * 2.2 / (total[t] + 1.2 * (.25 + .75 * sizes[session] / average))
                                  + 2 * (t in titles[session])) for t in matched)
            scores[session] = score * coverage
        for rank, session in enumerate(sorted(scores, key=lambda s: (-scores[s], s))[:limit], 1):
            entry = fused.setdefault(session, {"session": session, "fusion_score": 0, "matched_queries": [],
                                               "terms": set()})
            entry["fusion_score"] += 1 / (60 + rank)
            entry["matched_queries"].append(query_index + 1)
            entry["terms"].update(terms)
    ordered = sorted(fused.values(), key=lambda e: (-e["fusion_score"], e["session"]))[:limit]
    for entry in ordered:
        terms = entry.pop("terms")
        ranked = sorted((r for r in by_session[entry["session"]] if hot.get(id(r), {}).keys() & terms),
                        key=lambda r: (-len(hot[id(r)].keys() & terms), r["order"]))[:3]
        entry["evidence"] = [(row, terms) for row in sorted(ranked, key=lambda r: r["order"])]
    return ordered


PRIVATE = ("text", "order", "score", "coverage", "token_counts", "title", "render", "fetch", "length", "epoch", "system")


def evidence_hit(row, terms, query_index, coverage):
    hit = {key: value for key, value in (row["render"]() if "render" in row else {}).items() if key not in PRIVATE}
    for key, value in row.items():   # rendered fields win: rows keep only an index-time subset
        if key not in PRIVATE:
            hit.setdefault(key, value)
    text = text_of(row)
    hit.update(anchor_key=row.get("locator", {}).get("item_id", row.get("line")), excerpt=excerpt(text, terms),
               query_index=query_index, excerpt_offset=excerpt_start(text, terms), coverage=coverage)
    return hit


def retrieve(rows, queries, limit=5, roles="both", since=None, until=None, project=None, session=None):
    """Return distinct sessions with separately anchored supporting messages.

    Windows of up to three messages connect a topic, options and a short answer.
    Role/date/project/session filters apply to each message before indexing. Fusion uses
    ranks, never raw scores across queries. Sessions matched only as a whole fill the list
    after message matches. No lexical hit is a verified decision.

    Only windows holding a query term are materialized; the window count and mean length
    that BM25 needs are accumulated arithmetically. Rows may carry `token_counts` restricted
    to the query terms plus an explicit `length` (index-backed) or full counts (in memory).
    """
    language = backend("claude")
    selected = [r for r in rows if (roles == "both" or r["role"] == roles)
                and (not since or r["date"] >= since) and (not until or r["date"] <= until)
                and (not project or project.lower() in (r.get("project") or r.get("cwd") or "").lower())
                and (not session or r["session"].startswith(session))]
    normalized = [language.normalize_query(q) for q in queries]
    query_terms = {term for _, terms, _ in normalized for term in terms}
    hot, length = {}, {}
    for row in selected:
        counts = row["token_counts"] if "token_counts" in row else Counter(language.tokenize(row["text"]))
        length[id(row)] = row["length"] if "length" in row else sum(counts.values())
        found = {term: counts[term] for term in query_terms if term in counts}
        if found:
            hot[id(row)] = found
    sessions = defaultdict(list)
    for row in rows:
        sessions[row["session"]].append(row)
    unit_count = unit_length = 0
    units = {}   # (session order, end position, size) -> messages; tuple order = creation order
    for order, messages in enumerate(sessions.values()):
        messages.sort(key=lambda r: (r.get("timestamp", r.get("date", "")), r["order"]))
        # Never bridge a filtered-out turn or a different session.
        flags = [id(row) in length for row in messages]
        run = 0
        for i, row in enumerate(messages):
            run = run + 1 if flags[i] else 0
            if not run:
                continue
            size = length[id(row)]
            unit_count += 1
            unit_length += size
            if run >= 2:
                size += length[id(messages[i - 1])]
                unit_count += 1
                unit_length += size
                if run >= 3:
                    unit_count += 1
                    unit_length += size + length[id(messages[i - 2])]
            if id(row) in hot:
                for end in range(i, min(i + 3, len(messages))):
                    for width in range(end - i + 1, 4):
                        first = end - width + 1
                        if first >= 0 and all(flags[first:end + 1]):
                            units.setdefault((order, end, width), messages[first:end + 1])
    unit_counts, lengths, frequency = {}, {}, Counter()
    for key, unit in units.items():
        counts = {}
        for row in unit:
            for term, count in hot.get(id(row), {}).items():
                counts[term] = counts.get(term, 0) + count
        unit_counts[key] = counts
        lengths[key] = sum(length[id(row)] for row in unit)
        frequency.update(counts.keys())
    average = unit_length / max(1, unit_count) or 1
    fused = {}
    attempts = []
    for query_index, query in enumerate(queries):
        cleaned, terms, groups = normalized[query_index]
        # A term's bits are the concept groups it belongs to; a unit's coverage is the popcount
        # of its terms' bits. Only units over the gate are scored, in query-term order as before.
        bits = {term: sum(1 << g for g, group in enumerate(groups) if term in group) for term in terms}
        weight = {term: math.log(1 + (unit_count - frequency[term] + .5) / (frequency[term] + .5)) for term in terms}
        ranked = []
        for i, counts in unit_counts.items():
            mask = 0
            for term in counts:
                mask |= bits.get(term, 0)
            coverage = mask.bit_count() / max(1, len(groups))
            if coverage < .6:
                continue
            matched = {term for term in counts if term in bits}
            unit = units[i]
            # A window must contribute evidence beyond a single message.
            if len(unit) > 1 and any(matched <= hot.get(id(row), {}).keys() for row in unit):
                continue
            score, scale = 0.0, 1.5 * (.25 + .75 * lengths[i] / average)
            for term in terms:
                count = counts.get(term)
                if count:
                    score += weight[term] * count * 2.5 / (count + scale)
            ranked.append((score * coverage * (1.4 if any(r["role"] == "user" for r in unit) else 1), i, coverage))
        ranked.sort(key=lambda hit: (-hit[0], -hit[2], hit[1]))
        seen = set()
        for score, i, coverage in ranked:
            unit = units[i]
            owner = unit[0]["session"]
            if owner in seen:
                continue
            seen.add(owner)
            rank = len(seen)
            entry = fused.setdefault(owner, {"session": owner, "fusion_score": 0,
                                               "matched_queries": [], "evidence": []})
            entry["fusion_score"] += coverage ** 2 / (60 + rank)
            entry["matched_queries"].append(query_index + 1)
            for row in unit:
                anchor = row.get("locator", {}).get("item_id", row.get("line"))
                if any(e["anchor_key"] == anchor for e in entry["evidence"]):
                    continue
                entry["evidence"].append(evidence_hit(row, terms, query_index + 1, round(coverage, 3)))
        attempts.append({"query": language.redact(query), "matching_sessions": len(seen),
                         "searchable_terms": len(groups)})
    ordered = [dict(e, match="message") for e in
               sorted(fused.values(), key=lambda e: (-e["fusion_score"], e["session"]))[:limit]]
    if len(ordered) < limit:
        for entry in session_fill(selected, normalized, hot, length, fused.keys(), limit - len(ordered)):
            entry["evidence"] = [evidence_hit(row, terms, None, None) for row, terms in entry["evidence"]]
            ordered.append(dict(entry, match="session"))
    candidates = []
    for rank, entry in enumerate(ordered, 1):
        evidence = entry["evidence"][:6]
        messages = sessions[entry["session"]]
        opening = next((text_of(r) for r in messages if r["role"] == "user"), "")
        candidate = dict(evidence[0])
        candidate.update(rank=rank, fusion_score=round(entry["fusion_score"], 6), match=entry["match"],
                         title=next((r["title"] for r in messages if r.get("title")), None),
                         opening=" ".join(opening.split())[:200],
                         matched_queries=entry["matched_queries"], evidence=evidence)
        candidates.append(candidate)
    return {"status": "ambiguous" if candidates else
            "empty_query" if not any(a["searchable_terms"] for a in attempts) else "no_match",
            "candidates": candidates, "queries": attempts,
            "coverage": {"messages_available": len(rows), "messages_searched": len(selected),
                         "sessions_searched": len({r["session"] for r in selected}),
                         "roles": roles, "since": since, "until": until, "project": project, "session": session},
            "verification_required": True}


def search(source, queries, cwd, limit, roles, since=None, until=None, project=None, session=None):
    started = time.monotonic()
    rows, metadata = load(source, cwd, queries)
    result = retrieve(rows, queries, limit, roles, since, until, project, session)
    result.update(metadata, elapsed_ms=round((time.monotonic() - started) * 1000))
    return result


# Harness notices that carry no structural marker in the transcript (see the `system` field).
NOT_TYPED = ("another claude session sent a message", "[request interrupted by user",
             "your response above was stop", "(re-invocation of")
IMAGE_NOTICE = re.compile(r"^(?:\[image: [^\]]*\]\s*)+", re.I)


def list_window(rows, since, until=None, roles="user", project=None, session=None, limit=200, max_chars=500):
    """Messages inside [since, until] (epoch seconds) in time order, grouped by session.

    Takes no query: this answers "what was said then", which ranking cannot.
    """
    inside = sorted((r for r in rows if (roles == "both" or r["role"] == roles)
                     and since <= r["epoch"] and (until is None or r["epoch"] <= until)
                     and (not project or project.lower() in (r.get("project") or r.get("cwd") or "").lower())
                     and (not session or r["session"].startswith(session))),
                    key=lambda r: (r["epoch"], r["order"]))
    filtered, kept = 0, []
    for row in inside:
        text = IMAGE_NOTICE.sub("", " ".join(text_of(row).split()))
        if row["role"] == "user" and (row.get("system") or not text or text.lower().startswith(NOT_TYPED)):
            filtered += 1
            continue
        message = {"time": datetime.fromtimestamp(row["epoch"]).astimezone().isoformat(timespec="minutes"),
                   "role": row["role"], "text": text[:max_chars], "chars": len(text), "truncated": len(text) > max_chars}
        if "locator" in row:
            message["item_id"] = row["locator"]["item_id"]
        else:
            message["line"] = row["line"]
        kept.append((row, message))
    sessions = {}
    for row, message in kept[:limit]:
        sessions.setdefault(row["session"], {
            "session": row["session"], "title": row.get("title"), "project": row.get("project") or row.get("cwd"),
            "messages": []})["messages"].append(message)
    return {"status": "ok" if kept else "no_messages", "sessions": list(sessions.values()),
            "coverage": {"messages_available": len(rows), "messages_in_window": len(inside),
                         "messages_filtered": filtered, "messages_listed": len(kept[:limit]),
                         "messages_omitted": len(kept[limit:]), "sessions_listed": len(sessions), "roles": roles}}


def timeline(source, cwd, since, until=None, roles="user", project=None, session=None, limit=200, max_chars=500):
    started = time.monotonic()
    # Unlike search, keep the current session: its earlier requests may have left the context.
    rows, metadata = Index(source, backend).rows(cwd, set(), None)
    result = list_window(rows, since, until, roles, project, session, limit, max_chars)
    result.update(metadata, current_task_exclusion="included", elapsed_ms=round((time.monotonic() - started) * 1000))
    return result


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("codex", "claude"), required=True)
    parser.add_argument("--query", action="append")
    parser.add_argument("--timeline", action="store_true")
    parser.add_argument("--since-epoch", type=float)
    parser.add_argument("--until-epoch", type=float)
    parser.add_argument("--max-chars", type=int, default=500)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--roles", default="both")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--project")
    parser.add_argument("--session")
    args = parser.parse_args()
    try:
        output = (timeline(args.source, args.cwd, args.since_epoch, args.until_epoch, args.roles, args.project,
                           args.session, args.limit, args.max_chars) if args.timeline else
                  search(args.source, args.query, args.cwd, args.limit, args.roles, args.since, args.until,
                         args.project, args.session))
    except Exception as exc:
        output = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(output, ensure_ascii=False))
