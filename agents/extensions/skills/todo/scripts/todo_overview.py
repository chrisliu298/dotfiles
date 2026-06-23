#!/usr/bin/env python3
"""Render / check the derived Overview block in a todo ``TODO.md``.

Standard library only — no third-party deps, so any agent with a Python 3
interpreter can run it (no venv needed). The Overview is a deterministic
*projection* of the checklist (the source of truth). This script owns ONLY the
region between the ``TODO-OVERVIEW`` markers; everything else is echoed
byte-for-byte, so it can never clobber the hand-maintained checklist.

Subcommands:
  write <path>   Insert or replace the Overview block in place (idempotent).
  check <path>   Exit nonzero if the block is missing, stale, or the file is malformed.
  print <path>   Print the derived Overview block to stdout (no file edit).
  self-test      Run fixture-based tests; exit nonzero on failure.

Exit codes: 0 ok · 1 stale/missing (check) or test failure · 2 malformed/absent file.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
from datetime import datetime

# Bump when the rendered layout changes, so existing blocks re-render on next write.
FORMAT_VERSION = "1"

BEGIN_RE = re.compile(r"^<!--\s*TODO-OVERVIEW:BEGIN\b.*-->\s*$")
END_RE = re.compile(r"^<!--\s*TODO-OVERVIEW:END\s*-->\s*$")
SHA_RE = re.compile(r"input_sha=([0-9a-f]{12})")
ITEM_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.*\S)\s*$")
AREA_RE = re.compile(r"#area/([A-Za-z0-9][A-Za-z0-9_-]*)")
DONE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*[—-]\s*(.*)$")
SECTIONS = ("In Progress", "To Do", "Done")
END_MARKER = "<!-- TODO-OVERVIEW:END -->"
BAR_WIDTH = 10


class TodoError(Exception):
    """Malformed/absent input — abort without editing the file (exit 2)."""


# --- parsing --------------------------------------------------------------

def split_frontmatter(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise TodoError("missing YAML frontmatter (file must start with '---')")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], lines[i + 1:]
    raise TodoError("unterminated YAML frontmatter")


def parse_frontmatter(fm_lines):
    fields = {}
    for ln in fm_lines:
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", ln)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


def parse_items(body_lines):
    items = []
    seen_section = False
    current = None
    for ln in body_lines:
        h = re.match(r"^##\s+(.*\S)\s*$", ln)
        if h:
            name = h.group(1).strip()
            if name in SECTIONS:
                current, seen_section = name, True
            else:
                current = None
            continue
        m = ITEM_RE.match(ln)
        if m and current is not None:
            raw_text = m.group(2)
            areas = AREA_RE.findall(ln)
            if len(areas) > 1:
                raise TodoError("item has multiple #area/ tags: %r" % raw_text)
            items.append({
                "section": current,
                "done": m.group(1).lower() == "x",
                "area": areas[0] if areas else None,
                "text": AREA_RE.sub("", raw_text).strip(),
                "raw": ln.strip(),
            })
    return items, seen_section


# --- derivation -----------------------------------------------------------

def compute_sha(fields, items):
    parts = [
        "v=" + FORMAT_VERSION,
        "task=" + fields.get("task", ""),
        "started_at=" + fields.get("started_at", ""),
        "last_session=" + fields.get("last_session", ""),
    ]
    for it in items:
        parts.append("%s|%d|%s|%s" % (
            it["section"], int(it["done"]), it["area"] or "", it["text"]))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:12]


def area_display(slug):
    words = slug.replace("_", " ").replace("-", " ").split()
    return " ".join(w if w.isupper() else w.capitalize() for w in words)


def pct(done, total):
    return round(100 * done / total) if total else 0


def bar(done, total):
    frac = (done / total) if total else 0.0
    filled = max(0, min(BAR_WIDTH, round(frac * BAR_WIDTH)))
    return "[" + "#" * filled + "-" * (BAR_WIDTH - filled) + "]"


def day_span(a, b):
    try:
        return (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days
    except (ValueError, TypeError):
        return None


def render_overview(fields, items):
    total = len(items)
    done = sum(1 for it in items if it["done"])
    in_prog = sum(1 for it in items if it["section"] == "In Progress")
    todo = sum(1 for it in items if it["section"] == "To Do")
    progress = "**Progress:** %d/%d done (%d%%) `%s` · %d in progress · %d to do" % (
        done, total, pct(done, total), bar(done, total), in_prog, todo)

    buckets = {}
    for it in items:
        key = it["area"] or "__other__"
        b = buckets.setdefault(key, [0, 0])
        b[1] += 1
        if it["done"]:
            b[0] += 1

    def area_sort(kv):
        key, (d, t) = kv
        return (key == "__other__", -t, key)

    area_parts = ["%s %d/%d (%d%%)" % (
        "Other" if k == "__other__" else area_display(k), d, t, pct(d, t))
        for k, (d, t) in sorted(buckets.items(), key=area_sort)]
    areas = "**Areas:** " + (" · ".join(area_parts) if area_parts else "none")

    attn = []
    for it in items:
        if it["section"] == "Done":
            continue
        low = it["raw"].lower()
        if "blocked" in low or "waiting on" in low:
            label = area_display(it["area"]) if it["area"] else None
            attn.append("%s: %s" % (label, it["text"]) if label else it["text"])
    if attn:
        more = "; +%d more" % (len(attn) - 3) if len(attn) > 3 else ""
        needs = "**Needs attention:** %d — %s%s" % (len(attn), "; ".join(attn[:3]), more)
    else:
        needs = "**Needs attention:** none"

    done_dates = []
    for it in items:
        if it["section"] == "Done":
            m = DONE_DATE_RE.match(it["text"])
            if m:
                done_dates.append((m.group(1), m.group(2).strip()))
    bits = []
    if done_dates:
        done_dates.sort(key=lambda x: x[0])
        latest = done_dates[-1]
        bits.append("latest %s %s" % (latest[0], latest[1]) if latest[1] else "latest %s" % latest[0])
    else:
        bits.append("no completed items yet")
    started, last = fields.get("started_at", ""), fields.get("last_session", "")
    if started:
        bits.append("started %s" % started)
    if last:
        bits.append("last touched %s" % last)
    span = day_span(started, last)
    if span is not None:
        bits.append("%d-day span" % span)
    recent = "**Recent:** " + " · ".join(bits)

    return ["## Overview", progress, areas, needs, recent]


def begin_marker(input_sha, rendered_at):
    return "<!-- TODO-OVERVIEW:BEGIN input_sha=%s rendered_at=%s -->" % (input_sha, rendered_at)


def full_block(fields, items, input_sha, rendered_at):
    return [begin_marker(input_sha, rendered_at)] + render_overview(fields, items) + [END_MARKER]


# --- file location helpers ------------------------------------------------

def find_block(lines):
    begins = [i for i, ln in enumerate(lines) if BEGIN_RE.match(ln)]
    ends = [i for i, ln in enumerate(lines) if END_RE.match(ln)]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1:
        raise TodoError("malformed Overview markers (expected exactly one BEGIN and one END)")
    if begins[0] >= ends[0]:
        raise TodoError("Overview END marker precedes BEGIN")
    return (begins[0], ends[0])


def stored_sha(lines, span):
    m = SHA_RE.search(lines[span[0]])
    return m.group(1) if m else None


def frontmatter_end_index(lines):
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i
    raise TodoError("unterminated YAML frontmatter")


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise TodoError("%s not found; create the todo file first" % path)


def write_file(path, content):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".todo-overview.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="minutes")


def _load(path):
    text = read_file(path)
    lines = text.split("\n")
    fm_lines, body_lines = split_frontmatter(text)
    fields = parse_frontmatter(fm_lines)
    items, seen = parse_items(body_lines)
    if not seen:
        raise TodoError("no canonical sections found (## In Progress / ## To Do / ## Done)")
    return lines, fields, items


# --- commands -------------------------------------------------------------

def cmd_write(path):
    lines, fields, items = _load(path)
    cur = compute_sha(fields, items)
    span = find_block(lines)
    if span is not None:
        if stored_sha(lines, span) == cur:
            print("todo-overview: up to date (%s)" % cur)
            return 0
        block = full_block(fields, items, cur, now_iso())
        new_lines = lines[:span[0]] + block + lines[span[1] + 1:]
    else:
        block = full_block(fields, items, cur, now_iso())
        fe = frontmatter_end_index(lines)
        after = lines[fe + 1:]
        while after and after[0].strip() == "":
            after.pop(0)
        new_lines = lines[:fe + 1] + [""] + block + [""] + after
    write_file(path, "\n".join(new_lines))
    print("todo-overview: rendered (%s)" % cur)
    return 0


def cmd_check(path):
    lines, fields, items = _load(path)
    cur = compute_sha(fields, items)
    span = find_block(lines)
    if span is None:
        print("todo-overview: Overview block missing; run 'write'", file=sys.stderr)
        return 1
    if stored_sha(lines, span) != cur:
        print("todo-overview: Overview stale (block != checklist); run 'write'", file=sys.stderr)
        return 1
    print("todo-overview: fresh (%s)" % cur)
    return 0


def cmd_print(path):
    _, fields, items = _load(path)
    print("\n".join(full_block(fields, items, compute_sha(fields, items), now_iso())))
    return 0


# --- self-test ------------------------------------------------------------

def run_self_test():
    failures = []

    def ok(cond, msg):
        if not cond:
            failures.append(msg)

    d = tempfile.mkdtemp(prefix="todo-overview-test.")
    sample = (
        "---\n"
        "task: Migrate auth to OIDC\n"
        "started_at: 2026-05-01\n"
        "last_session: 2026-05-07\n"
        "---\n"
        "\n"
        "## In Progress\n"
        "- [ ] Wire up callback handler — blocked on infra ticket #4821 #area/backend\n"
        "\n"
        "## To Do\n"
        "- [ ] Update SDK consumers #area/sdk\n"
        "- [ ] Write rollback notes\n"
        "\n"
        "## Done\n"
        "- [x] 2026-05-01 — Spike OIDC vs SAML #area/backend\n"
        "- [x] 2026-05-02 — Provision IdP app #area/infra\n"
    )
    p = os.path.join(d, "TODO.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(sample)

    ok(cmd_write(p) == 0, "write returned nonzero")
    t1 = open(p, encoding="utf-8").read()
    ok("TODO-OVERVIEW:BEGIN" in t1 and END_MARKER in t1, "markers not inserted")
    ok("## Overview" in t1, "overview heading missing")
    ok("2/5 done (40%)" in t1, "progress wrong:\n" + t1)
    ok("Backend 1/2" in t1, "backend tally wrong")
    ok("Other 0/1" in t1, "untagged item not bucketed to Other")
    ok("- [ ] Wire up callback handler — blocked on infra ticket #4821 #area/backend" in t1,
       "checklist clobbered")

    cmd_write(p)
    ok(t1 == open(p, encoding="utf-8").read(), "second write not idempotent")
    ok(cmd_check(p) == 0, "check on fresh file failed")

    t3 = t1.replace("- [ ] Write rollback notes", "- [x] 2026-05-08 — Write rollback notes")
    with open(p, "w", encoding="utf-8") as f:
        f.write(t3)
    ok(cmd_check(p) == 1, "check did not detect stale")
    cmd_write(p)
    ok(cmd_check(p) == 0, "check not fresh after re-render")
    ok("3/5 done (60%)" in open(p, encoding="utf-8").read(), "progress not updated after edit")

    pbad = os.path.join(d, "BAD.md")
    with open(pbad, "w", encoding="utf-8") as f:
        f.write(sample.replace("#area/sdk", "#area/sdk #area/extra"))
    raised = False
    try:
        cmd_write(pbad)
    except TodoError:
        raised = True
    ok(raised, "multiple area tags not rejected")

    raised = False
    try:
        cmd_check(os.path.join(d, "NOPE.md"))
    except TodoError:
        raised = True
    ok(raised, "missing file not rejected")

    import shutil
    shutil.rmtree(d, ignore_errors=True)

    if failures:
        for m in failures:
            print("FAIL:", m, file=sys.stderr)
        print("todo-overview self-test: %d failure(s)" % len(failures), file=sys.stderr)
        return 1
    print("todo-overview self-test: all passed")
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    try:
        if cmd == "self-test":
            return run_self_test()
        if cmd in ("write", "check", "print"):
            if len(argv) < 2:
                print("todo-overview: '%s' needs a TODO.md path" % cmd, file=sys.stderr)
                return 2
            return {"write": cmd_write, "check": cmd_check, "print": cmd_print}[cmd](argv[1])
        print("todo-overview: unknown command %r" % cmd, file=sys.stderr)
        return 2
    except TodoError as e:
        print("todo-overview: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
