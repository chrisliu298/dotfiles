#!/usr/bin/env python3
"""docmaint — maintain one durable Markdown doc for the todo / exec-status / mental-seal skills.

ONE identical interface across three sibling skills. Each skill ships a byte-identical copy of
this file; the ONLY line that differs between copies is the ``DOC = "..."`` assignment below.
Standard library only — no venv, no third-party deps; a thin ``docmaint`` bash launcher execs it.

The script is an *accelerator, not the mechanism*: it owns only the deterministic parts (locating,
scaffolding, structural validation, the todo Overview projection, and timestamp bookkeeping). The
agent still authors all prose, all task items, all findings/Health, and the seal's priority — and,
crucially, decides whether the evidence was actually re-checked. The doc Markdown stays
hand-maintainable; an agent with no Python can follow the format documented in each SKILL.md.

Two-clock freshness (the honesty rule):
  * MECHANICAL stamps say only "the tool rendered/validated these bytes." Safe to auto-write.
      todo:   `rendered_at` inside the TODO-OVERVIEW marker (hash-gated by `input_sha`).
      others: `validated_at` inside a hidden `<!-- DOCMAINT … -->` comment, written by `sync`.
  * SEMANTIC stamps say "an agent re-checked reality." NEVER auto-written — moved ONLY by the
    `stamp` verb, which requires an explicit attestation plus the evidence boundary, and records a
    `freshness_sha` over the trust-bearing content. If that content later changes without a fresh
    attestation, `check --handoff` fails: a stale claim becomes an *explicit* false attestation,
    never a silent side effect.

Verbs (identical for all three docs):
    locate   [--path P] [--root D]                      print the resolved doc path
    scaffold [--path P] [--root D] [--force]            create from template if missing
    check    [--path P] [--root D] [--required]         the handoff GATE — never writes
                       [--handoff] [--strict-anchor] [--max-lines N]
    sync     [--path P] [--root D]                      deterministic rewrites + mechanical stamp
    stamp    [--path P] [--root D] --attest KIND …      the ONLY verb that moves semantic freshness
    print    [--path P] [--root D]                      print the derived/template view, no edit
    self-test                                           fixture tests (covers all three doc types)

Exit codes (identical for all three docs):
    0  ok / nothing to do / inactive (no doc found and not --required)
    1  actionable: missing-required, stale derived block, unattested/stale freshness under
       --handoff, missing anchor under --strict-anchor, placeholders remain
    2  malformed / unsafe location / bad arguments / would clobber authored content
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# DOC — the ONE line that differs between the three installed copies.
# todo/scripts → "todo" · exec-status/scripts → "status" · mental-seal/scripts → "seal"
DOC = "todo"
# ─────────────────────────────────────────────────────────────────────────────

# Contract fingerprint — asserted by self-test and diffed across the three copies by the
# repo drift-guard (dotfiles.sh lint). Bump only with a deliberate interface change.
CONTRACT = "docmaint/1 verbs=locate,scaffold,check,sync,stamp,print,self-test exit=0ok,1action,2malformed"

VERBS = ("locate", "scaffold", "check", "sync", "stamp", "print", "self-test")

DOC_CONFIG = {
    "todo":   {"filename": "TODO.md",   "attest": "flush",      "frontmatter": True},
    "status": {"filename": "STATUS.md", "attest": "rechecked",  "frontmatter": False},
    "seal":   {"filename": "SEAL.md",   "attest": "reconciled", "frontmatter": True},
}

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = {
    # todo is seeded inline (no template file); the others copy a committed template.
    "status": os.path.join(SKILL_DIR, "assets", "STATUS.template.md"),
    "seal":   os.path.join(SKILL_DIR, "SEAL.template.md"),
}

# Hidden machine-metadata comment (status/seal): mechanical `validated_at` + semantic
# `attested_at`/`freshness_sha`. An HTML comment, kept as the file's last line, so a human never
# conflates it with the visible `Fresh as of`.
META_RE = re.compile(r"^<!--\s*DOCMAINT\b(?P<body>.*?)-->\s*$", re.MULTILINE)
META_KV_RE = re.compile(r"(\w+)=(\S+)")

# todo Overview markers (unchanged from the original todo-overview, so existing TODO.md stay valid)
TODO_BEGIN_RE = re.compile(r"^<!--\s*TODO-OVERVIEW:BEGIN\b.*-->\s*$")
TODO_END_RE = re.compile(r"^<!--\s*TODO-OVERVIEW:END\s*-->\s*$")
TODO_END_MARKER = "<!-- TODO-OVERVIEW:END -->"
TODO_SHA_RE = re.compile(r"input_sha=([0-9a-f]{12})")
ITEM_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.*\S)\s*$")
AREA_RE = re.compile(r"#area/([A-Za-z0-9][A-Za-z0-9_-]*)")
DONE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*[—-]\s*(.*)$")
TODO_SECTIONS = ("In Progress", "To Do", "Done")
TODO_FORMAT_VERSION = "1"
BAR_WIDTH = 10

# status
STATUS_REQUIRED_SECTIONS = (
    "## Bottom line", "## Should you be worried?", "## What we've found so far",
    "## Where we are", "## How current is this", "## For the AI",
)
STATUS_REQUIRED_FIELDS = ("Health:", "Fresh as of:", "Last checked against:", "Out of date if:")
VALID_HEALTH = {"ON TRACK", "WATCH", "BLOCKED", "DONE", "UNKNOWN"}
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"<[^>\n]{3,}>")
HEALTH_RE = re.compile(r"^Health:\s*([A-Za-z ]+?)\s*(?:—|-|·|\n|$)", re.MULTILINE)
# Value regexes use [^\n]* / [ \t]* so they never cross or eat a newline.
FRESH_VAL_RE = re.compile(r"(Fresh as of:[ \t]*)([^\n]*?)([ \t]*)$", re.MULTILINE)
CHECKED_VAL_RE = re.compile(r"(Last checked against:[ \t]*)([^\n]*?)([ \t]*)$", re.MULTILINE)
OOD_VAL_RE = re.compile(r"(Out of date if:[ \t]*)([^\n]*?)([ \t]*)$", re.MULTILINE)

# seal
SEAL_VALID_STATUS = {"active", "released", "superseded", "needs_review"}
SEAL_REQUIRED_FM = ("id", "status", "set_by", "set_at", "priority", "purpose", "end_state",
                    "discharge_when", "expires_if")
HISTORY_SPLIT_RE = re.compile(r"(?m)^##\s+History\b")
SEAL_ANCHOR_RE = re.compile(r"<!--\s*mental-seal:start\s*-->")


class DocError(Exception):
    """Malformed/absent/unsafe input — abort without editing the file (exit 2)."""


# ── shared plumbing ─────────────────────────────────────────────────────────

def cfg(doc):
    return DOC_CONFIG[doc]


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="minutes")


def today():
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def now_human():
    # e.g. "2026-06-23 14:32 PDT" — matches the STATUS template's "Fresh as of" format.
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z").strip()


def sha12(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise DocError("%s not found" % path)


def write_file(path, content):
    """Atomic replace — same-dir temp + fsync + os.replace, so a crash never truncates the doc.
    Preserves the target's mode when it already exists; new files get 0644."""
    abspath = os.path.abspath(path)
    d = os.path.dirname(abspath) or "."
    try:
        mode = os.stat(abspath).st_mode & 0o777
    except OSError:
        mode = 0o644
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".docmaint.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, abspath)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def is_unsafe_root(d):
    d = os.path.realpath(d)
    home = os.path.realpath(os.path.expanduser("~"))
    tmp = os.path.realpath(tempfile.gettempdir())
    return d in (home, os.path.sep, tmp) or d.startswith(tmp + os.sep)


def find_project_root(start):
    """Nearest ancestor (incl. start) with .git / CLAUDE.md / AGENTS.md. Returns (root|None, chain)."""
    cur = os.path.realpath(start)
    chain = [cur]
    while os.path.dirname(chain[-1]) != chain[-1]:
        chain.append(os.path.dirname(chain[-1]))
    for anc in chain:
        if (os.path.isdir(os.path.join(anc, ".git"))
                or os.path.isfile(os.path.join(anc, "CLAUDE.md"))
                or os.path.isfile(os.path.join(anc, "AGENTS.md"))):
            return anc, chain
    return None, chain


def locate(doc, path_arg=None, root_arg=None):
    """Resolve the doc path. Returns (abspath, exists). Raises DocError (exit 2) when it would have
    to CREATE in an unsafe/unknown place.

    Rule (identical for all three): `--path` wins (explicit file, always honored). Else `--root/<file>`
    (honored if it exists; refused for creation in an unsafe root). Else search upward from cwd ONLY
    up to the nearest project root (.git/CLAUDE.md/AGENTS.md) for an existing file — so a nested
    project never grabs a parent's doc — and, if none, create at that root (refusing $HOME/temp/`/`).
    """
    filename = cfg(doc)["filename"]
    if path_arg:
        p = os.path.abspath(path_arg)
        return p, os.path.isfile(p)
    if root_arg:
        p = os.path.join(os.path.abspath(root_arg), filename)
        if os.path.isfile(p):
            return p, True
        if is_unsafe_root(os.path.abspath(root_arg)):
            raise DocError("refusing to create %s in unsafe root %s — pass --path for an explicit file" % (filename, root_arg))
        return p, False
    root, chain = find_project_root(os.getcwd())
    search = chain if root is None else chain[:chain.index(root) + 1]
    for anc in search:                      # an existing file within cwd..root wins
        cand = os.path.join(anc, filename)
        if os.path.isfile(cand):
            return cand, True
    if root is None:
        raise DocError("no project root for %s (no .git/CLAUDE.md/AGENTS.md upward) — pass --root or --path" % filename)
    if is_unsafe_root(root):
        raise DocError("refusing to create %s in unsafe project root %s — pass --root or --path" % (filename, root))
    return os.path.join(root, filename), False


def split_frontmatter(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise DocError("missing YAML frontmatter (file must start with '---')")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], lines[i + 1:], i
    raise DocError("unterminated YAML frontmatter")


def parse_frontmatter(fm_lines):
    """Minimal, quote-aware `key: value [# comment]` parser. A quoted value keeps everything
    inside the quotes (so `priority: "Fix #4821"` is NOT truncated at the #); an unquoted value
    has any trailing inline comment stripped."""
    fields = {}
    for ln in fm_lines:
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", ln)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith('"'):
            q = re.match(r'"((?:[^"\\]|\\.)*)"', raw)
            val = q.group(1) if q else raw.strip('"')
        else:
            val = raw.split("#", 1)[0].strip()
        fields[key] = val
    return fields


# ── hidden DOCMAINT metadata (status/seal) ───────────────────────────────────

def parse_meta(text):
    m = META_RE.search(text)
    if not m:
        return {}
    return dict(META_KV_RE.findall(m.group("body")))


def render_meta(meta):
    parts = " ".join("%s=%s" % (k, meta[k]) for k in ("validated_at", "attested_at", "freshness_sha") if meta.get(k))
    return "<!-- DOCMAINT %s -->" % parts


def upsert_meta(text, **updates):
    """Update the metadata, always collapsing it to exactly ONE comment as the final line — so a
    hand-introduced duplicate META can't survive a write, and the comment never drifts mid-file."""
    meta = parse_meta(text)
    meta.update({k: v for k, v in updates.items() if v is not None})
    body = strip_meta(text).rstrip("\n")
    return body + "\n" + render_meta(meta) + "\n"


def strip_meta(text):
    return META_RE.sub("", text)


def _normalize(text):
    """Collapse harmless formatting (trailing per-line whitespace, CRLF, trailing blank lines) so a
    pure reformat doesn't cry-wolf as a content change."""
    return "\n".join(ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n")).strip("\n")


def freshness_sha(doc, text):
    """Hash the trust-bearing content. Excludes ONLY the hidden META comment (which holds the hash
    itself). The visible freshness timestamp IS included — so a bare hand-edit of `Fresh as of` /
    `last_recalled` without a real `stamp` changes the hash and fails `check --handoff`. For a seal,
    the archival `## History` section is excluded (editing old records must not flag the active
    seal). Whitespace is normalized to avoid reformat-only false staleness."""
    body = strip_meta(text)
    if doc == "seal":
        body = HISTORY_SPLIT_RE.split(body, maxsplit=1)[0]
    return sha12(_normalize(body))


# ── output helper ─────────────────────────────────────────────────────────────

def emit(status, path, reason):
    # one-line, agent- and human-legible: "<doc>: <status>: <path> — <reason / next action>"
    sys.stdout.write("%s: %s: %s — %s\n" % (DOC, status, path, reason))


def emit_problems(path, problems, warnings):
    for w in warnings:
        sys.stdout.write("%s: warn: %s — %s\n" % (DOC, path, w))
    for p in problems:
        sys.stderr.write("%s: FAIL: %s — %s\n" % (DOC, path, p))


# ── todo: Overview projection (ported from todo-overview, behavior preserved) ──

def todo_parse_items(body_lines):
    items, seen, current = [], False, None
    for ln in body_lines:
        h = re.match(r"^##\s+(.*\S)\s*$", ln)
        if h:
            name = h.group(1).strip()
            current = name if name in TODO_SECTIONS else None
            if current:
                seen = True
            continue
        m = ITEM_RE.match(ln)
        if m and current is not None:
            raw_text = m.group(2)
            areas = AREA_RE.findall(ln)
            if len(areas) > 1:
                raise DocError("item has multiple #area/ tags: %r" % raw_text)
            items.append({
                "section": current, "done": m.group(1).lower() == "x",
                "area": areas[0] if areas else None,
                "text": AREA_RE.sub("", raw_text).strip(), "raw": ln.strip(),
            })
    return items, seen


def todo_input_sha(fields, items):
    parts = ["v=" + TODO_FORMAT_VERSION, "task=" + fields.get("task", ""),
             "started_at=" + fields.get("started_at", ""), "last_session=" + fields.get("last_session", "")]
    for it in items:
        parts.append("%s|%d|%s|%s" % (it["section"], int(it["done"]), it["area"] or "", it["text"]))
    return sha12("\n".join(parts))


def _area_display(slug):
    words = slug.replace("_", " ").replace("-", " ").split()
    return " ".join(w if w.isupper() else w.capitalize() for w in words)


def _pct(d, t):
    return round(100 * d / t) if t else 0


def _bar(d, t):
    filled = max(0, min(BAR_WIDTH, round((d / t if t else 0.0) * BAR_WIDTH)))
    return "[" + "#" * filled + "-" * (BAR_WIDTH - filled) + "]"


def _day_span(a, b):
    try:
        return (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days
    except (ValueError, TypeError):
        return None


def todo_render_overview(fields, items):
    total = len(items)
    done = sum(1 for it in items if it["done"])
    in_prog = sum(1 for it in items if it["section"] == "In Progress")
    todo_n = sum(1 for it in items if it["section"] == "To Do")
    progress = "**Progress:** %d/%d done (%d%%) `%s` · %d in progress · %d to do" % (
        done, total, _pct(done, total), _bar(done, total), in_prog, todo_n)
    buckets = {}
    for it in items:
        b = buckets.setdefault(it["area"] or "__other__", [0, 0])
        b[1] += 1
        b[0] += int(it["done"])
    area_parts = ["%s %d/%d (%d%%)" % ("Other" if k == "__other__" else _area_display(k), d, t, _pct(d, t))
                  for k, (d, t) in sorted(buckets.items(), key=lambda kv: (kv[0] == "__other__", -kv[1][1], kv[0]))]
    areas = "**Areas:** " + (" · ".join(area_parts) if area_parts else "none")
    attn = []
    for it in items:
        if it["section"] == "Done":
            continue
        if "blocked" in it["raw"].lower() or "waiting on" in it["raw"].lower():
            label = _area_display(it["area"]) if it["area"] else None
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
    span = _day_span(started, last)
    if span is not None:
        bits.append("%d-day span" % span)
    return ["## Overview", progress, areas, needs, "**Recent:** " + " · ".join(bits)]


def todo_load(path):
    text = read_file(path)
    lines = text.split("\n")
    fm_lines, body_lines, _ = split_frontmatter(text)
    fields = parse_frontmatter(fm_lines)
    items, seen = todo_parse_items(body_lines)
    if not seen:
        raise DocError("no canonical sections (## In Progress / ## To Do / ## Done)")
    return lines, fields, items


def todo_find_block(lines):
    begins = [i for i, ln in enumerate(lines) if TODO_BEGIN_RE.match(ln)]
    ends = [i for i, ln in enumerate(lines) if TODO_END_RE.match(ln)]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise DocError("malformed TODO-OVERVIEW markers (need exactly one BEGIN before one END)")
    return (begins[0], ends[0])


def todo_block(fields, items, input_sha):
    begin = "<!-- TODO-OVERVIEW:BEGIN input_sha=%s rendered_at=%s -->" % (input_sha, now_iso())
    return [begin] + todo_render_overview(fields, items) + [TODO_END_MARKER]


def todo_render(path):
    """sync for todo: insert/replace the Overview block, idempotent via input_sha. Returns
    (changed, sha)."""
    lines, fields, items = todo_load(path)
    cur = todo_input_sha(fields, items)
    span = todo_find_block(lines)
    if span is not None:
        m = TODO_SHA_RE.search(lines[span[0]])
        body_ok = ([ln.rstrip() for ln in lines[span[0] + 1:span[1]]]
                   == [e.rstrip() for e in todo_render_overview(fields, items)])
        if m and m.group(1) == cur and body_ok:   # also rewrite if the body was hand-edited
            return False, cur
        new_lines = lines[:span[0]] + todo_block(fields, items, cur) + lines[span[1] + 1:]
    else:
        fe = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        after = lines[fe + 1:]
        while after and after[0].strip() == "":
            after.pop(0)
        new_lines = lines[:fe + 1] + [""] + todo_block(fields, items, cur) + [""] + after
    write_file(path, "\n".join(new_lines))
    return True, cur


# ── per-doc check ─────────────────────────────────────────────────────────────

def check_todo(path, problems, warnings, opts):
    lines, fields, items = todo_load(path)
    cur = todo_input_sha(fields, items)
    span = todo_find_block(lines)
    sink = problems if opts.get("handoff") else warnings
    if span is None:
        sink.append("Overview block missing — run `sync`")
        return
    m = TODO_SHA_RE.search(lines[span[0]])
    if not m or m.group(1) != cur:
        sink.append("Overview stale (block != checklist) — run `sync`")
        return
    # input_sha matches; verify the rendered BODY wasn't hand-edited (the block is derived, not authored)
    if ([ln.rstrip() for ln in lines[span[0] + 1:span[1]]]
            != [e.rstrip() for e in todo_render_overview(fields, items)]):
        sink.append("Overview body hand-edited (doesn't match the checklist projection) — run `sync`")


def check_status(path, problems, warnings, opts):
    text = read_file(path)
    for s in STATUS_REQUIRED_SECTIONS:
        if s not in text:
            problems.append("missing section: %s" % s)
    for f in STATUS_REQUIRED_FIELDS:
        if f not in text:
            problems.append("missing field: %s" % f)
    body = COMMENT_RE.sub("", text)
    placeholders = PLACEHOLDER_RE.findall(body)
    if placeholders:
        problems.append("still a skeleton: %d unfilled placeholder(s) (e.g. %s)" % (len(placeholders), placeholders[0]))
        return
    m = HEALTH_RE.search(text)
    if m and m.group(1).strip().upper() not in VALID_HEALTH:
        problems.append("invalid Health %r — use one of %s" % (m.group(1).strip(), sorted(VALID_HEALTH)))
    if "Checked against:" not in text:
        warnings.append("findings have no 'Checked against:' handle")
    if "Confidence:" not in text:
        warnings.append("findings have no 'Confidence:' label")
    n_lines = text.count("\n") + 1
    ml = opts.get("max_lines", 60)
    if n_lines > ml * 2:
        problems.append("bloated: %d lines (>%d) — a STATUS.md is a fixed-size snapshot" % (n_lines, ml * 2))
    elif n_lines > ml:
        warnings.append("long: %d lines (>%d) — trim toward one screen" % (n_lines, ml))
    _check_freshness("status", text, problems, warnings, opts)


def check_seal(path, problems, warnings, opts):
    text = read_file(path)
    fm_lines, _body, _ = split_frontmatter(text)
    fields = parse_frontmatter(fm_lines)
    for f in SEAL_REQUIRED_FM:
        if f not in fields:
            problems.append("missing frontmatter field: %s" % f)
    status = fields.get("status", "")
    if status and status not in SEAL_VALID_STATUS:
        problems.append("invalid status %r — use one of %s" % (status, sorted(SEAL_VALID_STATUS)))
    # Count active seals only OUTSIDE the archival ## History section (whose records are prose, not
    # `status:` lines) — so an archived seal or example never trips a false "two active seals".
    pre_history = HISTORY_SPLIT_RE.split(text, maxsplit=1)[0]
    n_active = len(re.findall(r"(?m)^status:[ \t]*active\b", pre_history))
    if n_active > 1:
        problems.append("more than one active seal (%d) — exactly one allowed; supersede the rest" % n_active)
    body = COMMENT_RE.sub("", text)
    placeholders = PLACEHOLDER_RE.findall(body)
    if status == "active" and placeholders:
        problems.append("active seal still a skeleton: %d placeholder(s) (e.g. %s)" % (len(placeholders), placeholders[0]))
        return
    if not SEAL_ANCHOR_RE.search(read_root_instruction_files(path)):
        (problems if opts.get("strict_anchor") else warnings).append(
            "no `mental-seal` anchor in CLAUDE.md/AGENTS.md at the project root — install it once (see SKILL.md Setup)")
    if status == "active":
        _check_freshness("seal", text, problems, warnings, opts)


def _check_freshness(doc, text, problems, warnings, opts):
    """Semantic-freshness gate: the freshness_sha recorded at the last `stamp` must still match the
    current trust-bearing content. Warning by default; failure under --handoff."""
    field = "Fresh as of" if doc == "status" else "last_recalled"
    sink = problems if opts.get("handoff") else warnings
    metas = list(META_RE.finditer(text))
    if len(metas) > 1:
        problems.append("multiple DOCMAINT metadata comments (%d) — exactly one allowed; re-`stamp`/`sync` to collapse" % len(metas))
        return
    meta = parse_meta(text)
    cur = freshness_sha(doc, text)
    # An honest attestation requires BOTH stamps (only `stamp` writes attested_at), and the hash must match.
    if not meta.get("freshness_sha") or not meta.get("attested_at"):
        sink.append("'%s' never attested — run `stamp --attest %s …` after re-checking the evidence" % (field, cfg(doc)["attest"]))
    elif meta["freshness_sha"] != cur:
        sink.append("'%s' stale: trust-bearing content changed since the last attestation — re-check and `stamp` again" % field)
    elif metas and not META_RE.match(text.rstrip().rsplit("\n", 1)[-1]):
        warnings.append("DOCMAINT metadata isn't the final line — `sync` to move it to the end")


def read_root_instruction_files(seal_path):
    root = os.path.dirname(os.path.abspath(seal_path))
    out = []
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            try:
                out.append(read_file(p))
            except DocError:
                pass
    return "\n".join(out)


CHECKERS = {"todo": check_todo, "status": check_status, "seal": check_seal}


# ── per-doc sync (deterministic + mechanical stamp only) ──────────────────────

def sync_doc(doc, path):
    if doc == "todo":
        changed, sha = todo_render(path)
        return ("changed" if changed else "ok"), ("rendered Overview (%s)" % sha if changed else "Overview up to date (%s)" % sha)
    # status/seal: validate, then refresh only the mechanical `validated_at` in the hidden comment.
    problems, warnings = [], []
    CHECKERS[doc](path, problems, warnings, {"handoff": False})
    if any(p for p in problems if "stale" not in p and "never attested" not in p):
        raise DocError("refusing to sync — structure invalid: %s" % problems[0])
    text = read_file(path)
    new = upsert_meta(text, validated_at=now_iso())
    if new != text:
        write_file(path, new)
    return "ok", "validated; mechanical validated_at stamped (semantic freshness untouched — use `stamp`)"


# ── per-doc stamp (the ONLY verb that moves semantic freshness) ───────────────

def stamp_doc(doc, path, args):
    want = cfg(doc)["attest"]
    if args.get("attest") != want:
        raise DocError("%s stamp needs --attest %s (got %r)" % (doc, want, args.get("attest")))
    if doc == "todo":
        return _stamp_todo(path)
    if doc == "status":
        return _stamp_status(path, args)
    return _stamp_seal(path, args)


def _set_frontmatter_field(text, key, value):
    """Set a frontmatter field, operating ONLY within the leading `---`…`---` block so a same-named
    key in the body/History is never rewritten."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise DocError("no frontmatter to set %s" % key)
    fm_end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if fm_end is None:
        raise DocError("unterminated frontmatter")
    pat = re.compile(r"^(%s:[ \t]*).*$" % re.escape(key))
    for i in range(1, fm_end):
        if pat.match(lines[i]):
            lines[i] = pat.sub(lambda _m: "%s%s" % (_m.group(1), value), lines[i])
            return "\n".join(lines)
    lines.insert(fm_end, "%s: %s" % (key, value))
    return "\n".join(lines)


def _stamp_todo(path):
    text = _set_frontmatter_field(read_file(path), "last_session", today())
    write_file(path, text)
    _changed, sha = todo_render(path)
    return "changed", "flushed: last_session=%s; Overview re-rendered (%s)" % (today(), sha)


def _stamp_status(path, args):
    # The freshness trio travels together — require both evidence args so a stamp can't half-update it.
    if not args.get("checked_against") or not args.get("out_of_date_if"):
        raise DocError("status stamp needs --checked-against \"<evidence>\" AND --out-of-date-if \"<condition>\" (the freshness trio travels together)")
    text = read_file(path)
    if not (FRESH_VAL_RE.search(text) and CHECKED_VAL_RE.search(text) and OOD_VAL_RE.search(text)):
        raise DocError("can't find the freshness trio lines (Fresh as of / Last checked against / Out of date if) — scaffold or fix structure first")
    text = FRESH_VAL_RE.sub(lambda m: "%s%s" % (m.group(1), now_human()), text, count=1)
    text = CHECKED_VAL_RE.sub(lambda m: "%s%s" % (m.group(1), args["checked_against"]), text, count=1)
    text = OOD_VAL_RE.sub(lambda m: "%s%s" % (m.group(1), args["out_of_date_if"]), text, count=1)
    text = upsert_meta(text, attested_at=now_iso(), freshness_sha=freshness_sha("status", text))
    write_file(path, text)
    return "changed", "attested: Fresh as of=%s; freshness trio + checkpoint recorded" % now_human()


def _stamp_seal(path, args):
    if not args.get("against"):
        raise DocError("seal stamp needs --against \"<what you reconciled against>\"")
    text = read_file(path)
    text = _set_frontmatter_field(text, "last_recalled", today())
    text = _set_frontmatter_field(text, "last_recalled_against", '"%s"' % args["against"])
    text = upsert_meta(text, attested_at=now_iso(), freshness_sha=freshness_sha("seal", text))
    write_file(path, text)
    return "changed", "reconciled: last_recalled=%s; checkpoint recorded" % today()


# ── per-doc scaffold / print ──────────────────────────────────────────────────

TODO_SEED = """---
task: <one-line goal>
started_at: %s
last_session: %s
---

## In Progress
- [ ] <the immediate next step>

## To Do

## Done
"""


def scaffold_doc(doc, path, force):
    if os.path.exists(path) and not force:
        return "ok", "exists (not overwriting; pass --force to replace)"
    if doc == "todo":
        write_file(path, TODO_SEED % (today(), today()))
        return "changed", "seeded TODO.md — fill in `task` and the first step"
    tpl = TEMPLATE_PATH[doc]
    if not os.path.isfile(tpl):
        raise DocError("template not found at %s" % tpl)
    write_file(path, read_file(tpl))
    return "changed", "created from template — fill every <placeholder>, then it's ready"


def print_doc(doc, path):
    if doc == "todo":
        lines, fields, items = todo_load(path)
        # Deterministic preview: the BEGIN marker uses a fixed sentinel, not a live clock, so two
        # prints are identical and never imply a write happened.
        begin = "<!-- TODO-OVERVIEW:BEGIN input_sha=%s rendered_at=<preview> -->" % todo_input_sha(fields, items)
        return "\n".join([begin] + todo_render_overview(fields, items) + [TODO_END_MARKER])
    # status/seal have no derived region; print a validation summary. Deliberately do NOT print the
    # current freshness_sha — exposing a copy-pasteable hash would invite hand-forging the META.
    problems, warnings = [], []
    CHECKERS[doc](path, problems, warnings, {"handoff": False})
    return "%s: %d problem(s), %d warning(s) — run `check` for detail, `stamp` to attest freshness" % (
        doc, len(problems), len(warnings))


# ── command dispatch ──────────────────────────────────────────────────────────

def parse_args(argv):
    """Tiny flag parser (stdlib argparse would also do; kept explicit to share one shape)."""
    if not argv:
        raise DocError("usage: docmaint <%s> [--path P] [--root D] …" % "|".join(VERBS))
    verb = argv[0]
    opts = {"path": None, "root": None, "force": False, "required": False, "handoff": False,
            "strict_anchor": False, "max_lines": 60, "attest": None, "checked_against": None,
            "out_of_date_if": None, "against": None}
    val_flags = {"--path": "path", "--root": "root", "--attest": "attest",
                 "--checked-against": "checked_against", "--out-of-date-if": "out_of_date_if",
                 "--against": "against"}
    bool_flags = {"--force": "force", "--required": "required", "--handoff": "handoff",
                  "--strict-anchor": "strict_anchor"}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in val_flags:
            if i + 1 >= len(argv):
                raise DocError("missing value for %s" % a)
            opts[val_flags[a]] = argv[i + 1]; i += 2; continue
        if a in bool_flags:
            opts[bool_flags[a]] = True; i += 1; continue
        if a == "--max-lines":
            if i + 1 >= len(argv):
                raise DocError("missing value for --max-lines")
            try:
                opts["max_lines"] = int(argv[i + 1])
            except ValueError:
                raise DocError("--max-lines needs an integer, got %r" % argv[i + 1])
            i += 2; continue
        raise DocError("unknown argument: %s" % a)
    return verb, opts


def run(doc, argv):
    verb, opts = parse_args(argv)
    if verb == "self-test":
        return run_self_test()
    if verb not in VERBS:
        raise DocError("unknown verb %r — one of %s" % (verb, ", ".join(VERBS)))

    path, exists = locate(doc, opts["path"], opts["root"])

    if verb == "locate":
        emit("ok" if exists else "absent", path, "exists" if exists else "does not exist yet")
        return 0 if exists else 1

    if verb == "scaffold":
        status, reason = scaffold_doc(doc, path, opts["force"])
        emit(status, path, reason)
        return 0

    if not exists:
        if verb == "check" and not opts["required"]:
            emit("ok", path, "no doc found — inactive (pass --required to make this a failure)")
            return 0
        emit("absent", path, "does not exist — run `scaffold`")
        return 1

    if verb == "check":
        problems, warnings = [], []
        CHECKERS[doc](path, problems, warnings, opts)
        emit_problems(path, problems, warnings)
        if problems:
            return 1
        emit("ok", path, "check passed%s" % (" (handoff gate)" if opts["handoff"] else ""))
        return 0

    if verb == "sync":
        status, reason = sync_doc(doc, path)
        emit(status, path, reason)
        return 0

    if verb == "stamp":
        status, reason = stamp_doc(doc, path, opts)
        emit(status, path, reason)
        return 0

    if verb == "print":
        sys.stdout.write(print_doc(doc, path) + "\n")
        return 0
    return 2


def main(argv):
    try:
        return run(DOC, argv)
    except DocError as e:
        sys.stderr.write("%s: %s\n" % (DOC, e))
        return 2
    except (OSError, ValueError) as e:  # I/O or parse failure → clean exit 2, never a traceback
        sys.stderr.write("%s: error: %s\n" % (DOC, e))
        return 2


# ── self-test (covers all three doc types regardless of DOC) ──────────────────

def run_self_test():
    failures = []

    def ok(cond, msg):
        if not cond:
            failures.append(msg)

    # contract fingerprint guard
    ok(CONTRACT.split()[1] == "verbs=" + ",".join(VERBS), "CONTRACT verb list out of sync with VERBS")

    d = tempfile.mkdtemp(prefix="docmaint-test.")
    os.mkdir(os.path.join(d, ".git"))

    # ---- todo ----
    tp = os.path.join(d, "TODO.md")
    write_file(tp,
        "---\ntask: Migrate auth\nstarted_at: 2026-05-01\nlast_session: 2026-05-07\n---\n\n"
        "## In Progress\n- [ ] Wire callback — blocked on infra #4821 #area/backend\n\n"
        "## To Do\n- [ ] Update SDK #area/sdk\n- [ ] Rollback notes\n\n"
        "## Done\n- [x] 2026-05-01 — Spike #area/backend\n- [x] 2026-05-02 — Provision #area/infra\n")
    s, _r = sync_doc("todo", tp)
    ok(s == "changed", "todo sync should render")
    t1 = open(tp).read()
    ok("2/5 done (40%)" in t1, "todo progress wrong:\n" + t1)
    ok("Backend 1/2" in t1 and "Other 0/1" in t1, "todo area tally wrong")
    ok("- [ ] Wire callback — blocked on infra #4821 #area/backend" in t1, "todo checklist clobbered")
    ok(sync_doc("todo", tp)[0] == "ok", "todo sync should be idempotent")
    probs = []; check_todo(tp, probs, [], {"handoff": True}); ok(not probs, "fresh todo should pass")
    write_file(tp,t1.replace("- [ ] Rollback notes", "- [x] 2026-05-08 — Rollback notes"))
    probs = []; check_todo(tp, probs, [], {"handoff": True}); ok(probs, "edited todo should be stale under handoff")
    s, _r = stamp_doc("todo", tp, {"attest": "flush"}); ok(s == "changed", "todo flush stamp")
    ok("last_session: %s" % today() in open(tp).read(), "todo flush should set last_session")

    # ---- status ----
    sp = os.path.join(d, "STATUS.md")
    write_file(sp,
        "# STATUS — catch more fake reviews\n\n"
        "Health: WATCH — small win · Fresh as of: 2026-06-17 14:32 PT\n\n"
        "## Bottom line\nGoing okay.\n\n## Should you be worried?\nMildly.\n\n"
        "## What we've found so far\n- **Style signals help.** Checked against: exp 21. Confidence: moderate.\n\n"
        "## Where we are\n- Now: re-checking.\n- Needs a human? No.\n\n"
        "## How current is this\nLast checked against: exp 21.\nOut of date if: exp 22 lands.\n\n"
        "## For the AI — skip if human\n- maintain this.\n")
    probs, warns = [], []; check_status(sp, probs, warns, {"handoff": False})
    ok(not probs, "filled status should have no structure problems: %s" % probs)
    ok(any("never attested" in w for w in warns), "status should warn freshness not attested")
    probs = []; check_status(sp, probs, [], {"handoff": True})
    ok(any("never attested" in p for p in probs), "unattested status should FAIL under handoff")
    s, _r = sync_doc("status", sp); ok(s == "ok", "status sync ok")
    ok("validated_at=" in open(sp).read(), "status sync should write mechanical validated_at")
    ok("Fresh as of: 2026-06-17 14:32 PT" in open(sp).read(), "status sync must NOT move Fresh as of")
    s, _r = stamp_doc("status", sp, {"attest": "rechecked", "checked_against": "exp 23, commit abc",
                                     "out_of_date_if": "exp 24"})
    ok(s == "changed", "status stamp")
    txt = open(sp).read()
    ok("Last checked against: exp 23, commit abc" in txt, "status stamp should set checked-against")
    ok("freshness_sha=" in txt, "status stamp should record checkpoint")
    probs = []; check_status(sp, probs, [], {"handoff": True}); ok(not probs, "attested status passes handoff: %s" % probs)
    write_file(sp,open(sp).read().replace("Going okay.", "Going great now."))
    probs = []; check_status(sp, probs, [], {"handoff": True})
    ok(any("stale" in p for p in probs), "status edited after attestation should be stale under handoff")
    try:
        stamp_doc("status", sp, {"attest": "rechecked"}); ok(False, "status stamp without --checked-against must raise")
    except DocError:
        ok(True, "")
    # skeleton fails
    write_file(sp,"# STATUS — <goal>\n\nHealth: <X> · Fresh as of: <t>\n\n## Bottom line\n<x>\n"
                        "## Should you be worried?\n.\n## What we've found so far\n.\n## Where we are\n.\n"
                        "## How current is this\nLast checked against: .\nOut of date if: .\n## For the AI\n.\n")
    probs = []; check_status(sp, probs, [], {"handoff": False}); ok(any("skeleton" in p for p in probs), "skeleton status should fail")

    # ---- seal ----
    write_file(os.path.join(d, "CLAUDE.md"), "# proj\n<!-- mental-seal:start -->\nx\n<!-- mental-seal:end -->\n")
    sealp = os.path.join(d, "SEAL.md")
    write_file(sealp,
        "---\nid: 2026-06-23-ship\nstatus: active\nscope: project\nset_by: user\nset_at: 2026-06-23\n"
        "priority: \"Ship the migration\"\npurpose: \"unblock release\"\nend_state: \"all tests pass\"\n"
        "discharge_when: \"deployed\"\nexpires_if: \"goal changes\"\nsupersedes: null\nlast_recalled: null\n---\n\n"
        "# THE SEAL\n## Litany\nI hold one thing.\n## Commander's intent\n- Purpose: x\n## If-then wards\n- IF x THEN y\n## History\n")
    probs, warns = [], []; check_seal(sealp, probs, warns, {"handoff": False})
    ok(not probs, "valid seal should pass structure: %s" % probs)
    ok(any("never attested" in w for w in warns), "seal should warn freshness not attested")
    s, _r = stamp_doc("seal", sealp, {"attest": "reconciled", "against": "tests pass at commit abc"})
    ok(s == "changed", "seal stamp")
    txt = open(sealp).read()
    ok("last_recalled: %s" % today() in txt, "seal stamp should set last_recalled")
    ok("last_recalled_against:" in txt and "freshness_sha=" in txt, "seal stamp should set against + checkpoint")
    probs = []; check_seal(sealp, probs, [], {"handoff": True}); ok(not probs, "attested seal passes handoff: %s" % probs)
    # two active seals (a second active block BEFORE ## History — archived seals live in History as prose)
    write_file(sealp, txt.replace("## History", "---\nid: dup\nstatus: active\n---\n\n## History"))
    probs = []; check_seal(sealp, probs, [], {"handoff": False}); ok(any("active seal" in p for p in probs), "two active seals should fail")
    # missing anchor
    os.remove(os.path.join(d, "CLAUDE.md"))
    write_file(sealp,txt)
    probs, warns = [], []; check_seal(sealp, probs, warns, {"strict_anchor": True})
    ok(any("anchor" in p for p in probs), "missing anchor should fail under --strict-anchor")

    # ---- locate ----
    sub = os.path.join(d, "a", "b"); os.makedirs(sub)
    cwd = os.getcwd()
    try:
        os.chdir(sub)
        p, ex = locate("todo")
        ok(os.path.realpath(p) == os.path.realpath(tp) and ex, "locate should find TODO.md upward from a subdir")
    finally:
        os.chdir(cwd)
    # locate must NOT cross into a parent project: a nested project with its own root finds its own doc
    inner = os.path.join(d, "nested"); os.makedirs(os.path.join(inner, ".git"))
    itp = os.path.join(inner, "TODO.md"); write_file(itp, "---\ntask: inner\n---\n## In Progress\n## To Do\n## Done\n")
    try:
        os.chdir(inner)
        p, ex = locate("todo")
        ok(os.path.realpath(p) == os.path.realpath(itp), "nested locate must find the inner TODO.md, not the parent's")
    finally:
        os.chdir(cwd)
    # locate refuses to CREATE in an unsafe root (e.g. the temp dir) when no file exists
    try:
        locate("status", root_arg=os.path.join(d, "no-such-status-dir-XYZ"))
        ok(False, "locate should refuse to create in an unsafe --root")
    except DocError:
        ok(True, "")

    # ---- adversarial / regression (the review's findings) ----
    # B1: hand-bumping ONLY the visible freshness timestamp must NOT pass the gate
    write_file(sp, "# STATUS — x\n\nHealth: WATCH — w · Fresh as of: 2026-06-17 14:32 PT\n\n"
        "## Bottom line\nGoing okay.\n\n## Should you be worried?\nMildly.\n\n"
        "## What we've found so far\n- **S.** Checked against: exp 21. Confidence: moderate.\n\n"
        "## Where we are\n- Now: x.\n- Needs a human? No.\n\n"
        "## How current is this\nLast checked against: exp 21.\nOut of date if: exp 22.\n\n## For the AI\n- m.\n")
    stamp_doc("status", sp, {"attest": "rechecked", "checked_against": "exp 21", "out_of_date_if": "exp 22"})
    probs = []; check_status(sp, probs, [], {"handoff": True}); ok(not probs, "freshly stamped status passes")
    bumped = re.sub(r"Fresh as of: .*", "Fresh as of: 2027-01-01 09:00 PT", open(sp).read(), count=1)
    write_file(sp, bumped)
    probs = []; check_status(sp, probs, [], {"handoff": True})
    ok(any("stale" in p for p in probs), "B1: hand-bumped 'Fresh as of' must FAIL the handoff gate")
    # seal: hand-bumping last_recalled must fail; editing ## History must NOT
    write_file(sealp,
        "---\nid: x\nstatus: active\nscope: project\nset_by: user\nset_at: 2026-06-23\n"
        "priority: \"Ship\"\npurpose: \"x\"\nend_state: \"x\"\ndischarge_when: \"x\"\nexpires_if: \"x\"\n"
        "supersedes: null\nlast_recalled: null\n---\n\n# S\n## If-then wards\n- IF x THEN y\n## History\n")
    stamp_doc("seal", sealp, {"attest": "reconciled", "against": "checked"})
    after = open(sealp).read()
    probs = []; check_seal(sealp, probs, [], {"handoff": True}); ok(not probs, "freshly stamped seal passes")
    write_file(sealp, after.replace("## History", "## History\n- 2026-01-01-old — released 2026-01-02 — priority: \"old\""))
    probs = []; check_seal(sealp, probs, [], {"handoff": True}); ok(not probs, "editing ## History must NOT flag the active seal")
    write_file(sealp, re.sub(r"last_recalled: .*", "last_recalled: 2027-01-01", after, count=1))
    probs = []; check_seal(sealp, probs, [], {"handoff": True})
    ok(any("stale" in p for p in probs), "B1: hand-bumped 'last_recalled' must FAIL the handoff gate")
    # duplicate META is detected
    write_file(sp, open(sp).read() + "\n<!-- DOCMAINT validated_at=2020-01-01T00:00+00:00 -->\n")
    probs = []; check_status(sp, probs, [], {"handoff": False}); ok(any("multiple DOCMAINT" in p for p in probs), "duplicate META must be flagged")
    # corrupted Overview body with matching input_sha: check flags it, sync repairs it
    ttext = open(tp).read()
    corrupt = re.sub(r"\*\*Progress:\*\*[^\n]*", "**Progress:** TOTALLY BOGUS", ttext, count=1)
    write_file(tp, corrupt)
    probs = []; check_todo(tp, probs, [], {"handoff": True}); ok(any("hand-edited" in p for p in probs), "corrupted Overview body must be caught even when input_sha matches")
    ok(sync_doc("todo", tp)[0] == "changed", "sync must repair a hand-edited Overview body")
    probs = []; check_todo(tp, probs, [], {"handoff": True}); ok(not probs, "repaired Overview passes")
    # quote-aware frontmatter: a '#' inside a quoted value is preserved
    qf = parse_frontmatter(['priority: "Fix #4821 now"', 'status: active   # a comment'])
    ok(qf.get("priority") == "Fix #4821 now", "quoted '#' must be preserved: %r" % qf.get("priority"))
    ok(qf.get("status") == "active", "unquoted inline comment must be stripped: %r" % qf.get("status"))
    # parse_args: missing option value → DocError (clean exit 2), not a traceback
    try:
        parse_args(["check", "--path"]); ok(False, "missing --path value must raise DocError")
    except DocError:
        ok(True, "")
    # status stamp requires the full trio
    try:
        stamp_doc("status", sp, {"attest": "rechecked", "checked_against": "x"}); ok(False, "status stamp without --out-of-date-if must raise")
    except DocError:
        ok(True, "")

    import shutil
    shutil.rmtree(d, ignore_errors=True)

    if failures:
        for m in failures:
            if m:
                sys.stderr.write("FAIL: %s\n" % m)
        sys.stderr.write("docmaint self-test: %d failure(s)\n" % len([f for f in failures if f]))
        return 1
    sys.stdout.write("docmaint self-test: all passed (todo/status/seal)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
