#!/usr/bin/env python3
"""Deterministic helper for the exec-status skill.

Owns only the mechanical parts of maintaining STATUS.md — scaffolding the template and
validating structure. It never writes prose, and it does not stamp the time: a timestamp
must only move when the model has re-checked the evidence boundary alongside it, so the
model writes `Fresh as of` itself. Standard library only.

Usage:
    python status_check.py scaffold [path]                    # create STATUS.md from the template if missing
    python status_check.py check    [path] [--max-age-min N] [--max-lines N]

Default path is ./STATUS.md. `check` exits non-zero on a structural problem (missing
section/field, unfilled placeholders, invalid Health value) so it can be used as a
self-gate at a checkpoint. Staleness is opt-in (`--max-age-min`) and only ever a warning,
because this skill is event-driven, not clock-driven.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

DEFAULT_PATH = "STATUS.md"
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "STATUS.template.md"

REQUIRED_SECTIONS = [
    "## Bottom line",
    "## Should you be worried?",
    "## What we've found so far",
    "## Where we are",
    "## How current is this",
    "## For the AI",
]
REQUIRED_FIELDS = ["Health:", "Fresh as of:", "Last checked against:", "Out of date if:"]
VALID_HEALTH = {"ON TRACK", "WATCH", "BLOCKED", "DONE", "UNKNOWN"}

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"<[^>\n]{3,}>")
HEALTH_RE = re.compile(r"^Health:\s*([A-Za-z ]+?)\s*(?:—|-|·|\n|$)", re.MULTILINE)
FRESH_RE = re.compile(r"Fresh as of:\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")


def cmd_scaffold(path: Path) -> int:
    if path.exists():
        print(f"exists: {path} (not overwriting)")
        return 0
    if not TEMPLATE.exists():
        print(f"error: template not found at {TEMPLATE}", file=sys.stderr)
        return 2
    path.write_text(TEMPLATE.read_text())
    print(f"created: {path} (fill in every <placeholder>, then it's ready)")
    return 0


def cmd_check(path: Path, max_age_min: int | None, max_lines: int) -> int:
    if not path.exists():
        print(f"FAIL: {path} does not exist", file=sys.stderr)
        return 1
    text = path.read_text()
    problems: list[str] = []
    warnings: list[str] = []

    for s in REQUIRED_SECTIONS:
        if s not in text:
            problems.append(f"missing section: {s}")
    for f in REQUIRED_FIELDS:
        if f not in text:
            problems.append(f"missing field: {f}")

    # Unfilled template placeholders mean the report is still a skeleton — a hard fail,
    # not a warning, because a "passing" skeleton is exactly what erodes trust. Strip HTML
    # comments first so the template's continuation note isn't mistaken for a placeholder.
    body = COMMENT_RE.sub("", text)
    placeholders = PLACEHOLDER_RE.findall(body)
    is_skeleton = bool(placeholders)
    if is_skeleton:
        problems.append(
            f"still a skeleton: {len(placeholders)} unfilled placeholder(s) remain "
            f"(e.g. {placeholders[0]}) — fill them in"
        )

    # Finer checks only make sense on a filled report.
    if not is_skeleton:
        m = HEALTH_RE.search(text)
        if m:
            val = m.group(1).strip().upper()
            if val not in VALID_HEALTH:
                problems.append(f"invalid Health value {val!r} — use one of {sorted(VALID_HEALTH)}")
        if max_age_min is not None:
            fm = FRESH_RE.search(text)
            if not fm:
                warnings.append("couldn't parse 'Fresh as of' time for the staleness check")
            else:
                try:
                    # NOTE: assumes STATUS.md was stamped on this host's local clock; the age
                    # is approximate across machines or a DST boundary.
                    t = time.strptime(fm.group(1), "%Y-%m-%d %H:%M")
                    age = (time.time() - time.mktime(t)) / 60.0
                    if age > max_age_min:
                        warnings.append(f"possibly abandoned: last freshened {age:.0f} min ago (>{max_age_min})")
                    else:
                        print(f"fresh: {age:.0f} min old")
                except ValueError:
                    warnings.append(f"unparseable 'Fresh as of' time: {fm.group(1)!r}")

    n_lines = text.count("\n") + 1
    hard = max_lines * 2
    if n_lines > hard:
        problems.append(f"bloated: {n_lines} lines (>{hard}) — a STATUS.md is a fixed-size snapshot, not a log; cut it back")
    elif n_lines > max_lines:
        warnings.append(f"long: {n_lines} lines (>{max_lines}) — trim toward one screen")

    for w in warnings:
        print(f"warn: {w}")
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print("ok: structure check passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="exec-status STATUS.md helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("scaffold")
    ps.add_argument("path", nargs="?", default=DEFAULT_PATH)
    pc = sub.add_parser("check")
    pc.add_argument("path", nargs="?", default=DEFAULT_PATH)
    pc.add_argument("--max-age-min", type=int, default=None)
    pc.add_argument("--max-lines", type=int, default=60)
    args = ap.parse_args()

    path = Path(args.path)
    if args.cmd == "scaffold":
        return cmd_scaffold(path)
    if args.cmd == "check":
        return cmd_check(path, args.max_age_min, args.max_lines)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
