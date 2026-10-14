#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Audit safeguards refusals across the Claude Code sessions of one project.

Reads the local session transcripts (~/.claude/projects/<project>/*.jsonl) and
prints, without echoing any transcript content beyond short command heads:

  1. per session: requests on the target model, refusals, rate, and when an
     instructions attachment containing --marker (a new rule) first loaded;
  2. the refusal rate before vs after that load, with the Poisson probability
     of seeing at most the observed refusals at the old rate;
  3. stopped replies: the model that was running when the client reported one,
     and whether the tool calls of the stopped reply still ran;
  4. one block per refusal: entry of the turn, position in the turn, distance
     from the last compaction, and the tool calls/result sizes just before it.

  refusal-audit.py [--project DIR] [--since ISO] [--marker TEXT] [--context N]
"""

import argparse
import glob
import json
import math
import os
from collections import defaultdict

REFUSAL_NOTICE = "Your response above was stopped by a safety classifier"
ENTRY_TAGS = {
    "<cross-session-message": "cross-session",
    "<task-notification": "task-notification",
    "<command-name": "slash-command",
    "<local-command": "slash-command",
}


def project_dir(cwd):
    return os.path.expanduser("~/.claude/projects/" + cwd.replace("/", "-").replace(".", "-"))


def text_of(content):
    if isinstance(content, str):
        return content
    return "".join(c.get("text", "") for c in content or [] if c.get("type") == "text")


def entry_kind(content):
    s = text_of(content).lstrip()
    for tag, kind in ENTRY_TAGS.items():
        if tag in s[:200]:
            return kind
    return "system" if s.startswith("<system-reminder") else "user"


def result_size(c):
    x = c.get("content")
    return len(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False))


def tool_head(c):
    inp = c.get("input") or {}
    s = inp.get("command") or inp.get("file_path") or inp.get("pattern") or inp.get("to") or ""
    return f"{c['name']}: {' '.join(str(s).split())[:80]}"


def stopped_replies(records, since):
    """The client's own "stopped by a safety classifier" notices: which model was
    running, and whether the tool calls of the stopped reply still ran.

    Not the same count as the refusal markers: a marker is written only when the
    session was on the pinned model (so stops on the fallback model are missing
    from it) and carries direction=retry, so it belongs to a later request than
    the reply that was cut.
    """
    ordered = sorted((r for r in records if r.get("timestamp")), key=lambda r: r["timestamp"])
    ran = {
        c.get("tool_use_id")
        for r in ordered
        if r.get("type") == "user"
        for c in (r.get("message") or {}).get("content") or []
        if isinstance(c, dict) and c.get("type") == "tool_result"
    }
    out = []
    for i, r in enumerate(ordered):
        if r.get("type") != "user" or (r["timestamp"] or "")[:19] < since[:19]:
            continue
        if REFUSAL_NOTICE not in text_of((r.get("message") or {}).get("content")):
            continue
        prev = next(
            (
                q
                for q in reversed(ordered[:i])
                if q.get("type") == "assistant"
                and ((q.get("message") or {}).get("model") or "").startswith("claude-")
            ),
            None,
        )
        calls = []
        if prev:
            calls = [
                c
                for q in ordered
                if q.get("requestId") and q.get("requestId") == prev.get("requestId")
                for c in (q.get("message") or {}).get("content") or []
                if c.get("type") == "tool_use"
            ]
        out.append({
            "t": r["timestamp"][:19],
            "model": ((prev or {}).get("message") or {}).get("model") or "<unknown>",
            "calls": [(c["name"], c.get("id") in ran) for c in calls],
        })
    return out


def poisson_cdf(k, lam):
    return sum(math.exp(-lam) * lam**i / math.factorial(i) for i in range(k + 1))


def audit(path, args):
    title, rule_at, last_compact = os.path.basename(path)[:8], None, None
    seen, turn_entry, turn_reqs, since_compact = set(), None, 0, 0
    reqs = []  # timestamps of target-model requests
    flags, recent = [], []  # recent: (kind, detail) of the last tool calls/results
    records = []
    for line in open(path, errors="ignore"):
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    # A refused reply is retracted: its partial messages are neither a request nor prior context.
    retracted = {u for r in records for u in r.get("retractedMessageUuids") or []}
    flagged = set()
    for r in records:
        if r.get("uuid") in retracted:
            continue
        t = (r.get("timestamp") or "")[:19]
        if r.get("type") == "custom-title":
            title = r.get("customTitle") or title
        a = r.get("attachment") or {}
        if args.marker and rule_at is None and a.get("type") == "instructions" and args.marker in json.dumps(a, ensure_ascii=False):
            rule_at = t
        if t < args.since[:19]:
            continue
        sub = r.get("subtype") or ""
        m = r.get("message") or {}
        if sub == "compact_boundary":
            last_compact, since_compact, turn_entry, turn_reqs = t, 0, "compaction", 0
        elif sub.startswith("model_refusal"):
            if r.get("originalModel") != args.model or r.get("requestId") in flagged:
                continue
            flagged.add(r.get("requestId"))
            flags.append({
                "t": t, "cat": r.get("apiRefusalCategory"), "entry": turn_entry, "pos": turn_reqs,
                "since_compact": since_compact, "compact_at": last_compact, "recent": recent[-args.context:],
            })
        elif m.get("role") == "assistant" and m.get("model") != "<synthetic>" and m.get("id") not in seen:
            seen.add(m.get("id"))
            turn_reqs += 1
            since_compact += 1
            if m.get("model") == args.model:
                reqs.append(t)
        if m.get("role") == "assistant":
            recent += [("call", tool_head(c)) for c in m.get("content") or [] if c.get("type") == "tool_use"]
        elif r.get("type") == "user" and not r.get("isCompactSummary"):
            content = m.get("content")
            results = [c for c in content if c.get("type") == "tool_result"] if isinstance(content, list) else []
            recent += [("result", f"{result_size(c)} chars") for c in results]
            if not results and text_of(content).strip() and not text_of(content).startswith(REFUSAL_NOTICE):
                turn_entry, turn_reqs = entry_kind(content), 0
                recent.append(("entry", f"{turn_entry} {len(text_of(content))} chars"))
        recent = recent[-50:]
    return title, rule_at, reqs, flags, stopped_replies(records, args.since)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", default=project_dir(os.getcwd()))
    p.add_argument("--since", default="2026-10-12T18:48:00Z")
    p.add_argument("--marker", default="", help="text that only the new instructions contain")
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--context", type=int, default=8, help="tool calls/results shown before each refusal")
    args = p.parse_args()

    rows, total = [], defaultdict(int)
    for path in sorted(glob.glob(os.path.join(args.project, "*.jsonl"))):
        title, rule_at, reqs, flags, stops = audit(path, args)
        if not reqs and not flags and not stops:
            continue
        rows.append((title, rule_at, reqs, flags, stops))
        split = rule_at or "9"
        total["req_before"] += sum(t < split for t in reqs)
        total["req_after"] += sum(t >= split for t in reqs)
        total["flag_before"] += sum(f["t"] < split for f in flags)
        total["flag_after"] += sum(f["t"] >= split for f in flags)

    print(f"since {args.since}, model {args.model}" + (f", rule marker {args.marker!r}" if args.marker else ""))
    print(f"{'session':28} {'requests':>8} {'refusals':>8} {'rate':>7}  {'rule loaded':20} last request")
    for title, rule_at, reqs, flags, _ in sorted(rows, key=lambda x: -len(x[2])):
        rate = f"{100 * len(flags) / len(reqs):.2f}%" if reqs else "-"
        print(f"{title[:28]:28} {len(reqs):8} {len(flags):8} {rate:>7}  {(rule_at or '-')[:19]:20} {(reqs[-1] if reqs else '-')[:19]}")

    if args.marker:
        rb, ra, fb, fa = (total[k] for k in ("req_before", "req_after", "flag_before", "flag_after"))
        if rb and ra:
            old = fb / rb
            print(f"\nbefore rule: {fb}/{rb} = {100 * old:.2f}%   after rule: {fa}/{ra} = {100 * fa / ra:.2f}%")
            print(f"P(<= {fa} refusals in {ra} requests at the old rate) = {poisson_cdf(fa, old * ra):.3f}")

    stops = [s for _, _, _, _, st in rows for s in st]
    markers = sum(len(fl) for _, _, _, fl, _ in rows)
    if stops:
        by_model = defaultdict(lambda: [0, 0, 0])  # stops, tool calls in them, calls that ran
        for s in stops:
            row = by_model[s["model"]]
            row[0] += 1
            row[1] += len(s["calls"])
            row[2] += sum(ok for _, ok in s["calls"])
        print(f"\nstopped replies: {len(stops)} (refusal markers: {markers}; a marker needs the pinned model)")
        print(f"{'model running':22} {'stopped':>8} {'tool calls':>11} {'of those ran':>13}")
        for model, (n, c, ok) in sorted(by_model.items(), key=lambda x: -x[1][0]):
            print(f"{model:22} {n:8} {c:11} {ok:13}")
        names = defaultdict(int)
        for s in stops:
            for name, ok in s["calls"]:
                if ok:
                    names[name] += 1
        if names:
            print("executed from a stopped reply: " + ", ".join(f"{n}x {k}" for k, n in sorted(names.items(), key=lambda x: -x[1])))

    events = sorted(((f, title) for title, _, _, fl, _ in rows for f in fl), key=lambda x: x[0]["t"])
    for f, title in events:
        print(f"\n== {f['t'][:19]}Z {title} [{f['cat']}] entry={f['entry']} request #{f['pos'] + 1} of turn, "
              f"{f['since_compact']} requests after compaction {(f['compact_at'] or '-')[:19]}")
        for kind, detail in f["recent"]:
            print(f"   {kind:6} {detail}")


if __name__ == "__main__":
    main()
