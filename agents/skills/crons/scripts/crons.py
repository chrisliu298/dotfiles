#!/usr/bin/env python3
"""crons — a durable, version-controlled manifest for Claude Code recurring crons.

WHY THIS EXISTS (empirically verified against the live harness, 2026-06-25):
  * Recurring crons created via CronCreate are SESSION-ONLY. `durable: true` is silently
    ignored — nothing is written to `.claude/scheduled_tasks.json` (GitHub #40228) — so a
    force-quit, reboot, or `.claude/` wipe loses every cron with no harness-side recovery.
  * The harness AUTO-EXPIRES every recurring cron after 7 days.
  * `CronList` TRUNCATES the prompt and HUMANIZES the schedule ("Every day at 4:17 AM", not
    "17 4 * * *"), and its job IDs are ephemeral (change on every re-arm).
  => The live cron state is lossy and unrecoverable. The ONLY durable record of a cron's
     verbatim prompt + raw schedule is a file on disk. This tool makes `crons/*.cron` the
     SOURCE OF TRUTH and renders a human-readable CRONS.md from it.

THE LOAD-BEARING CONTRACT — PREPARER, NEVER ACTUATOR:
  This script does ONLY what a portable, side-effect-free program can: parse the manifest,
  render CRONS.md, gate staleness, and EMIT the exact harness calls to run. It NEVER calls
  CronCreate/CronList/CronDelete (those are Claude-only tools) and so CANNOT verify what is
  actually armed. The Claude agent is the sole actuator: it runs CronList, pipes the output
  to `reconcile`, and executes the emitted CronCreate/CronDelete calls itself.

NO FALSE ASSURANCE (the cardinal rule, the inverse of the docmaint freshness gate):
  Because the tool cannot see live state, it NEVER says a cron is "armed". `check` validates
  only that the SOURCE files and CRONS.md agree ("source consistent"), and `reconcile`
  reports only presence-BY-PURPOSE (the armed prompt/schedule are unverifiable). A green
  check over zero armed crons is exactly the trap this design avoids.

VERBS
    scaffold  [--root D]              create crons/ + an example .cron if missing
    render    [--root D]              parse crons/*.cron -> rewrite CRONS.md (pure, idempotent)
    check     [--root D]              fail-closed: do the .cron files and CRONS.md agree?
    reconcile [--root D] [--rearm-all]
                                      read a CronList dump on STDIN, match by purpose, and
                                      emit the exact CronDelete/CronCreate calls to run
    self-test                         stdlib fixture tests

EXIT CODES (uniform)
    0  ok / in sync / nothing to do
    1  actionable: CRONS.md stale (check), or live drift detected (reconcile)
    2  malformed / bad arguments / unsafe location
"""
from __future__ import annotations

import glob
import os
import re
import sys

CONTRACT = "crons/1 verbs=scaffold,render,check,reconcile,self-test exit=0ok,1action,2malformed"

REQUIRED_KEYS = ("schedule", "purpose", "recurring")
VALID_TARGETS = ("claude", "shell")
SEP = "\n---\n"

RENDER_BANNER = "# CRONS.md — recurring-cron manifest (SCRIPT-RENDERED by the `crons` skill — do NOT hand-edit)"


class CronError(Exception):
    """Malformed input or unsafe operation -> exit 2."""


# ── helpers ──────────────────────────────────────────────────────────────────

def norm_ws(s: str) -> str:
    """Collapse all whitespace runs to single spaces and strip — the matching normal form."""
    return re.sub(r"\s+", " ", s).strip()


def find_root(explicit: str | None) -> str:
    """Resolve the project root that holds (or will hold) crons/ + CRONS.md.

    --root wins. Otherwise search upward from cwd for a dir containing crons/ or .git;
    fall back to cwd. Never returns $HOME or / as an implicit root (refuse to scatter a
    manifest at the filesystem/home root) — even when $HOME itself is a git repo."""
    if explicit:
        root = os.path.abspath(explicit)
        if not os.path.isdir(root):
            raise CronError("--root %r is not a directory" % explicit)
        return root
    cur = os.getcwd()
    home = os.path.expanduser("~")
    d = cur
    while True:
        if d not in (home, "/") and (os.path.isdir(os.path.join(d, "crons")) or os.path.isdir(os.path.join(d, ".git"))):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    if cur in (home, "/"):
        raise CronError("refusing to use %r as a project root; pass --root or cd into a project" % cur)
    return cur


def crons_dir(root: str) -> str:
    return os.path.join(root, "crons")


def manifest_path(root: str) -> str:
    return os.path.join(root, "CRONS.md")


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_cron_file(path: str) -> dict:
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as fh:
        txt = fh.read().replace("\r\n", "\n").replace("\r", "\n")  # tolerate CRLF/CR files
    head, sep, body = txt.partition(SEP)
    if not sep:
        raise CronError("%s: missing the '---' line separating metadata from the prompt" % name)
    meta: dict[str, str] = {}
    for line in head.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise CronError("%s: metadata line without ':' -> %r" % (name, line))
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    for req in REQUIRED_KEYS:
        if req not in meta:
            raise CronError("%s: missing required key %r" % (name, req))
    prompt = body.strip()
    if not prompt:
        raise CronError("%s: empty prompt body (after the '---')" % name)
    recurring = meta["recurring"].lower()
    if recurring not in ("true", "false"):
        raise CronError("%s: recurring must be true|false, got %r" % (name, meta["recurring"]))
    target = meta.get("target", "claude").lower()
    if target not in VALID_TARGETS:
        raise CronError("%s: target must be one of %s, got %r" % (name, "|".join(VALID_TARGETS), target))
    return {
        "file": name,
        "schedule": meta["schedule"],
        "purpose": meta["purpose"],
        "recurring": recurring,
        "target": target,
        "prompt": prompt,
    }


def load_crons(root: str) -> list[dict]:
    cdir = crons_dir(root)
    if not os.path.isdir(cdir):
        raise CronError("no crons/ directory at %s — run `crons scaffold` first" % root)
    files = sorted(glob.glob(os.path.join(cdir, "*.cron")))
    if not files:
        raise CronError("no crons/*.cron files in %s" % cdir)
    crons = [parse_cron_file(f) for f in files]
    purposes = [c["purpose"] for c in crons]
    dups = {p for p in purposes if purposes.count(p) > 1}
    if dups:
        raise CronError("duplicate purpose(s) across .cron files: %s — purpose is the join key, keep it unique"
                        % ", ".join(sorted(dups)))
    return crons


# ── render ───────────────────────────────────────────────────────────────────

def render(crons: list[dict]) -> str:
    def esc(s: str) -> str:
        return s.replace("|", "\\|")  # keep Markdown table cells from breaking on a literal pipe

    L: list[str] = [RENDER_BANNER, ""]
    L += [
        "> **Source of truth = `crons/*.cron`.** Edit those, then run `crons render`. This file is a",
        "> generated projection for humans; never hand-edit it.",
        ">",
        "> **The live crons are SESSION-ONLY and unrecoverable from the harness:** `durable:true` is",
        "> ignored (no `scheduled_tasks.json` is written — GitHub #40228), `CronList` truncates the",
        "> prompt and humanizes the schedule, IDs are ephemeral, and every recurring cron auto-expires",
        "> after 7 days. So this file is the ONLY durable record of each verbatim prompt + raw schedule.",
        "",
        "## For the AI — recovery (do this on session start, after a compaction, or after a 7-day expiry)",
        "",
        "1. Run **CronList** (the tool).",
        "2. Pipe its output to **`crons reconcile`** (the literal text `No scheduled jobs.` = cold start = arm all;",
        "   an empty/unrecognized input is a fail-closed error, never a silent arm-all):",
        "   ```",
        "   crons reconcile <<'DUMP'",
        "   <paste the CronList output here, verbatim>",
        "   DUMP",
        "   ```",
        "3. Execute the emitted calls. For each `▶ ARM` block, call `CronCreate` with the shown `cron` +",
        "   `recurring`, and the prompt = the lines **between `>>> BEGIN PROMPT` and `>>> END PROMPT`,",
        "   copied EXACTLY** (they are flush-left — do not add indentation). Run `✖ CronDelete` lines as shown.",
        "4. Re-run **CronList** to confirm. NOTE: `CronDelete` can fail to stick (GitHub #49198) — if a",
        "   job keeps appearing, restart the session to clear it.",
        "",
        "This tool is a **preparer, never an actuator**: it cannot call the `Cron*` tools and therefore",
        "**cannot verify what is actually armed** — only presence by purpose. It never claims a cron is",
        "\"armed\"; treat a green `crons check` as \"source files agree\", not \"crons are running\".",
        "",
        "## Schedule (fire order within the hour)",
        "",
        "| # | Purpose | Schedule | Target | Recurring |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(crons, 1):
        L.append("| %d | %s | `%s` | %s | %s |" % (i, esc(c["purpose"]), esc(c["schedule"]), c["target"], c["recurring"]))
    L += ["", "## Verbatim prompts / commands (the durable record — re-arm from here)", ""]
    for i, c in enumerate(crons, 1):
        kind = "shell command" if c["target"] == "shell" else "prompt"
        L.append("### %d. %s — `%s` (target: %s, recurring: %s)" % (i, c["purpose"], c["schedule"], c["target"], c["recurring"]))
        L.append("")
        L.append("```")
        L.append(c["prompt"])
        L.append("```")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


# ── CronList dump parsing ────────────────────────────────────────────────────

# The empty-schedule sentinel as CronList prints it — anchored to a WHOLE line (MULTILINE) so a
# prompt that merely contains the phrase "no scheduled jobs" cannot masquerade as a cold start.
_EMPTY_DUMP_RE = re.compile(r"^\s*no scheduled jobs\.?\s*$", re.IGNORECASE | re.MULTILINE)
# A dump line: "<id> — <humanized schedule> (recurring) [session-only]: <truncated prompt>"
# Separator class covers em-dash, en-dash, and hyphen (humanizer variants).
_LINE_RE = re.compile(r"^(?P<id>\S+)\s+[—–-]\s+(?P<rest>.*)$")
# prompt starts after the status bracket "...]: " (preferred) else after the first ": " (colon-space).
_PROMPT_AFTER_BRACKET_RE = re.compile(r"\]\s*:\s(?P<prompt>.*)$")
_PROMPT_AFTER_COLON_RE = re.compile(r":\s(?P<prompt>.*)$")
_ELLIPSIS_RE = re.compile(r"(?:…|\.\.\.)\s*$")


def parse_cronlist_dump(text: str) -> list[dict]:
    """Parse pasted CronList output into [{id, prompt_prefix, raw}]. Tolerant of noise lines.

    Does NOT interpret emptiness — returning [] means "no parseable cron lines", which the caller
    must disambiguate (the literal 'No scheduled jobs.' sentinel = cold start; anything else = a
    fail-closed error, never a silent arm-all)."""
    out: list[dict] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        rest = m.group("rest")
        pm = _PROMPT_AFTER_BRACKET_RE.search(rest) or _PROMPT_AFTER_COLON_RE.search(rest)
        prompt = pm.group("prompt") if pm else ""
        prefix = norm_ws(_ELLIPSIS_RE.sub("", prompt))
        out.append({"id": m.group("id"), "prompt_prefix": prefix, "raw": line})
    return out


def match_dump(crons: list[dict], dump: list[dict]) -> dict:
    """Join the manifest (claude target) against the dump by purpose = prompt prefix.

    A dump entry matches a manifest cron when the (truncated) dump prompt is a prefix of the
    manifest's full prompt (whitespace-normalized). Returns matched/missing/extra/duplicate."""
    claude_crons = [c for c in crons if c["target"] == "claude"]
    norm_prompt = {c["purpose"]: norm_ws(c["prompt"]) for c in claude_crons}
    # for each dump entry, which manifest purposes does it prefix-match?
    entry_matches: list[tuple[dict, list[str]]] = []
    for e in dump:
        pfx = e["prompt_prefix"]
        hits = [c["purpose"] for c in claude_crons if pfx and norm_prompt[c["purpose"]].startswith(pfx)]
        entry_matches.append((e, hits))
    # per manifest cron, the dump entries that matched it
    per_cron: dict[str, list[dict]] = {c["purpose"]: [] for c in claude_crons}
    ambiguous: list[dict] = []
    for e, hits in entry_matches:
        if len(hits) == 1:
            per_cron[hits[0]].append(e)
        elif len(hits) > 1:
            ambiguous.append({"entry": e, "purposes": hits})
    amb_purposes = {p for a in ambiguous for p in a["purposes"]}
    matched_entry_ids = {e["id"] for e, hits in entry_matches if len(hits) == 1}
    hit_entry_ids = {e["id"] for e, hits in entry_matches if hits}  # matched some purpose (single OR ambiguous)
    extra = [e for e, hits in entry_matches if not hits]
    # A purpose that only matched AMBIGUOUSLY is NOT "missing" — arming it would risk a duplicate of
    # the live copy. Surface it via the ambiguous warning instead; never emit an ARM for it.
    missing = [c for c in claude_crons if not per_cron[c["purpose"]] and c["purpose"] not in amb_purposes]
    present = [c for c in claude_crons if len(per_cron[c["purpose"]]) == 1]
    duplicate = [{"cron": c, "entries": per_cron[c["purpose"]]} for c in claude_crons if len(per_cron[c["purpose"]]) > 1]
    return {
        "present": present, "missing": missing, "extra": extra,
        "duplicate": duplicate, "ambiguous": ambiguous,
        "matched_entry_ids": matched_entry_ids, "hit_entry_ids": hit_entry_ids,
    }


# ── reconcile output ─────────────────────────────────────────────────────────

def _arm_block(c: dict) -> list[str]:
    # The prompt is emitted FLUSH-LEFT between the markers (no added indent) so an agent copying it
    # verbatim into CronCreate cannot pick up phantom leading spaces.
    return [
        "▶ ARM (missing): %s" % c["purpose"],
        "   CronCreate(",
        '     cron      = "%s"' % c["schedule"],
        "     recurring = %s" % c["recurring"],
        "     prompt    = the lines between the markers below, copied EXACTLY (do not reindent)",
        "   )",
        ">>> BEGIN PROMPT",
        *c["prompt"].splitlines(),
        ">>> END PROMPT",
        "",
    ]


def reconcile_report(crons: list[dict], dump: list[dict], rearm_all: bool) -> tuple[str, int]:
    res = match_dump(crons, dump)
    cold = not dump
    L: list[str] = []
    drift = False

    L.append("=== crons reconcile ===")
    L.append("COLD START — no live crons; arming the full claude fleet." if cold
             else "Matched the live CronList dump against the manifest by purpose (prompt prefix).")
    L.append("")

    if rearm_all:
        # Full resync: delete every matched live copy by id, then arm every claude cron.
        L.append("MODE: --rearm-all (full resync — use after editing prompts/schedules, since the")
        L.append("tool cannot detect an edited prompt; it can only see presence by purpose).")
        L.append("")
        # Delete EVERY live copy that matched a manifest purpose (single or ambiguous), then re-create
        # all claude crons. True extras (matched nothing) are NOT deleted — they may be intentional;
        # surface them as advisory so a resync never silently removes an unmanaged cron.
        del_ids = sorted(res["hit_entry_ids"])
        for did in del_ids:
            L.append("✖ CronDelete(id=%s)" % did)
        if del_ids:
            L.append("")
        for c in [c for c in crons if c["target"] == "claude"]:
            L += _arm_block(c)
        for e in res["extra"]:
            L.append('⚠ EXTRA (armed but not in manifest — left as-is): id=%s "%s" — CronDelete only if unwanted.'
                     % (e["id"], e["prompt_prefix"][:60]))
        drift = True
    else:
        for c in res["missing"]:
            L += _arm_block(c)
            drift = True
        for d in res["duplicate"]:
            ids = [e["id"] for e in d["entries"]]
            L.append("⚠ DUPLICATE (%d copies armed): %s — keep one, delete the rest:" % (len(ids), d["cron"]["purpose"]))
            for did in ids[1:]:
                L.append("   ✖ CronDelete(id=%s)" % did)
            L.append("")
            drift = True
        for e in res["extra"]:
            L.append('⚠ EXTRA (armed but not in manifest): id=%s "%s"' % (e["id"], e["prompt_prefix"][:60]))
            L.append("   If unwanted: ✖ CronDelete(id=%s).  If it should persist: add a crons/*.cron for it." % e["id"])
            L.append("")
            drift = True
        for a in res["ambiguous"]:
            L.append('⚠ AMBIGUOUS: dump id=%s prefix-matches multiple purposes %s — prompts share a prefix;'
                     % (a["entry"]["id"], ", ".join(a["purposes"])))
            L.append("   make the first line of each prompt distinct so purpose stays a unique key.")
            L.append("")
            drift = True
        for c in res["present"]:
            L.append("✓ present (by purpose): %s  — armed prompt/schedule NOT verifiable (see note)" % c["purpose"])

    shell = [c for c in crons if c["target"] == "shell"]
    if shell:
        L.append("")
        L.append("· shell-target jobs (NOT armed via Claude — run them as OS timers; the v1 emitter is not built yet):")
        for c in shell:
            L.append("    - %s  (`%s`)" % (c["purpose"], c["schedule"]))

    L.append("")
    L.append("-- standing notes --")
    L.append("• This tool cannot verify live state. \"present\" means a job with that purpose exists; it does")
    L.append("  NOT confirm the armed prompt or schedule matches the manifest. Nothing here means \"armed\".")
    L.append("• After running CronDeletes, re-run CronList to confirm removal. CronDelete can fail to stick")
    L.append("  (GitHub #49198) — if a job keeps firing, restart the session to clear it.")
    L.append("• Recurring crons auto-expire after 7 days — re-run this reconcile periodically.")
    L.append("• To apply an EDITED prompt/schedule, use `crons reconcile --rearm-all` (delete + re-create).")

    return "\n".join(L).rstrip() + "\n", (1 if drift else 0)


# ── commands ─────────────────────────────────────────────────────────────────

EXAMPLE_CRON = """\
schedule: 7 * * * *
purpose: example heartbeat
recurring: true
target: claude
---
Example recurring task (replace me). Do one small thing and stop. Report one line only.
"""


def cmd_scaffold(args) -> int:
    root = find_root(args.get("root"))
    cdir = crons_dir(root)
    made = False
    if not os.path.isdir(cdir):
        os.makedirs(cdir)
        made = True
    existing = glob.glob(os.path.join(cdir, "*.cron"))
    if not existing:
        example = os.path.join(cdir, "01-example.cron")
        with open(example, "w", encoding="utf-8") as fh:
            fh.write(EXAMPLE_CRON)
        made = True
        print("wrote %s" % example)
    if made:
        print("scaffolded crons/ at %s — edit the .cron files, then run `crons render`." % root)
    else:
        print("crons/ already present at %s (%d .cron file(s))" % (root, len(existing)))
    return 0


def cmd_render(args) -> int:
    root = find_root(args.get("root"))
    crons = load_crons(root)
    out = render(crons)
    with open(manifest_path(root), "w", encoding="utf-8") as fh:
        fh.write(out)
    print("rendered %s from %d crons/*.cron file(s)" % (manifest_path(root), len(crons)))
    return 0


def cmd_check(args) -> int:
    root = find_root(args.get("root"))
    crons = load_crons(root)  # raises CronError (->2) on malformed sources
    want = render(crons)
    mp = manifest_path(root)
    if not os.path.exists(mp):
        print("CRONS.md MISSING — run `crons render`", file=sys.stderr)
        return 1
    with open(mp, encoding="utf-8") as fh:
        have = fh.read()
    if have.strip() != want.strip():
        print("CRONS.md STALE vs crons/*.cron — run `crons render`", file=sys.stderr)
        return 1
    print("source consistent: CRONS.md matches %d crons/*.cron file(s). "
          "(This does NOT mean any cron is armed — run `reconcile` for that.)" % len(crons))
    return 0


def cmd_reconcile(args) -> int:
    root = find_root(args.get("root"))
    crons = load_crons(root)
    dump_text = "" if sys.stdin.isatty() else sys.stdin.read()
    # Fail closed: an empty stdin (forgot to pipe) or an unrecognized non-empty dump must NEVER be
    # silently treated as a cold start — that would arm the whole fleet on top of live crons.
    if not dump_text.strip():
        raise CronError(
            "no CronList dump on stdin. Run the CronList tool and pipe its output:\n"
            "      crons reconcile <<'DUMP'\n      <paste CronList output>\n      DUMP\n"
            "  A genuinely empty schedule is the literal text 'No scheduled jobs.' — pipe that to cold-start.")
    dump = parse_cronlist_dump(dump_text)
    if not dump and not _EMPTY_DUMP_RE.search(dump_text):
        raise CronError(
            "could not parse any cron line from the input, and it is not the 'No scheduled jobs.' "
            "empty-sentinel — refusing to treat unrecognized input as a cold start (it would re-arm the "
            "whole fleet). Paste CronList output verbatim.")
    report, rc = reconcile_report(crons, dump, rearm_all=args.get("rearm_all", False))
    sys.stdout.write(report)
    return rc


# ── self-test ────────────────────────────────────────────────────────────────

def cmd_selftest(_args) -> int:
    import tempfile

    failures: list[str] = []

    def ok(cond, msg):
        if not cond:
            failures.append(msg)

    # parse + validate
    with tempfile.TemporaryDirectory() as d:
        cdir = os.path.join(d, "crons")
        os.makedirs(cdir)
        with open(os.path.join(cdir, "01-wd.cron"), "w") as fh:
            fh.write("schedule: 3,33 * * * *\npurpose: GPU watchdog\nrecurring: true\n---\n"
                     "GPU watchdog (ICR). Run nvidia-smi and report. Then stop.")
        with open(os.path.join(cdir, "02-disk.cron"), "w") as fh:
            fh.write("schedule: 18,48 * * * *\npurpose: disk-floor guard\nrecurring: true\ntarget: shell\n---\n"
                     "df -h /mnt/data1")
        crons = load_crons(d)
        ok(len(crons) == 2, "load_crons count")
        ok(crons[0]["target"] == "claude", "default target = claude")
        ok(crons[1]["target"] == "shell", "explicit target = shell")

        # render is pure / idempotent and check passes after render
        r1 = render(crons)
        r2 = render(crons)
        ok(r1 == r2, "render is deterministic")
        with open(manifest_path(d), "w") as fh:
            fh.write(r1)
        ok(cmd_check({"root": d}) == 0, "check passes on freshly rendered manifest")

        # malformed -> CronError
        with open(os.path.join(cdir, "03-bad.cron"), "w") as fh:
            fh.write("purpose: no schedule\nrecurring: true\n---\nx")
        try:
            load_crons(d)
            ok(False, "malformed .cron should raise")
        except CronError:
            ok(True, "")
        os.remove(os.path.join(cdir, "03-bad.cron"))

    # dump parsing: truncation + humanized schedule with an embedded colon (4:17)
    dump = parse_cronlist_dump(
        "0192d26b — Every day at 4:17 AM (recurring) [session-only]: GPU watchdog (ICR). Run nvidia-sm…"
    )
    ok(len(dump) == 1 and dump[0]["id"] == "0192d26b", "dump: id parsed")
    ok(dump[0]["prompt_prefix"].startswith("GPU watchdog (ICR). Run nvidia-sm"), "dump: prompt prefix, ellipsis stripped")
    ok(parse_cronlist_dump("No scheduled jobs.") == [], "dump: empty sentinel")
    ok(parse_cronlist_dump("") == [], "dump: blank")

    # matching: present (truncated prefix matches), missing, extra, cold start
    crons = [
        {"file": "1", "schedule": "3 * * * *", "purpose": "GPU watchdog", "recurring": "true",
         "target": "claude", "prompt": "GPU watchdog (ICR). Run nvidia-smi and report. Then stop."},
        {"file": "2", "schedule": "9 * * * *", "purpose": "docs", "recurring": "true",
         "target": "claude", "prompt": "Docs update. Reconcile STATUS.md. Then stop."},
    ]
    res = match_dump(crons, dump)
    ok([c["purpose"] for c in res["present"]] == ["GPU watchdog"], "match: watchdog present by prefix")
    ok([c["purpose"] for c in res["missing"]] == ["docs"], "match: docs missing")
    ok(res["extra"] == [], "match: no extras")

    extra_dump = parse_cronlist_dump("0aaa1111 — Every hour (recurring) [session-only]: Some other job not in manifest…")
    res2 = match_dump(crons, extra_dump)
    ok(len(res2["extra"]) == 1 and res2["extra"][0]["id"] == "0aaa1111", "match: extra detected")
    ok(len(res2["missing"]) == 2, "match: all missing when none match")

    rep, rc = reconcile_report(crons, dump, rearm_all=False)
    ok(rc == 1, "reconcile rc=1 on drift (docs missing)")
    ok("ARM (missing): docs" in rep, "reconcile emits ARM for missing")
    ok("present (by purpose): GPU watchdog" in rep, "reconcile reports present")
    _body = rep.split("-- standing notes --")[0].lower()
    ok("✓ armed" not in _body and "is armed" not in _body, "reconcile never positively claims a cron is armed")

    rep_cold, rc_cold = reconcile_report(crons, [], rearm_all=False)
    ok(rc_cold == 1 and "COLD START" in rep_cold, "reconcile cold start arms all")

    # fully in sync -> rc 0
    full_dump = parse_cronlist_dump(
        "0192d26b — x (recurring) [session-only]: GPU watchdog (ICR). Run nvidia…\n"
        "03330000 — x (recurring) [session-only]: Docs update. Reconcile STATUS…"
    )
    _, rc_sync = reconcile_report(crons, full_dump, rearm_all=False)
    ok(rc_sync == 0, "reconcile rc=0 when fully in sync")

    # --- regression tests for the code-review findings ---

    # (1) an ambiguous prefix-match must NOT be reported as missing (would arm a duplicate)
    amb_crons = [
        {"file": "1", "schedule": "1 * * * *", "purpose": "docs-a", "recurring": "true",
         "target": "claude", "prompt": "Docs update. Reconcile the ledger. Then stop."},
        {"file": "2", "schedule": "2 * * * *", "purpose": "docs-b", "recurring": "true",
         "target": "claude", "prompt": "Docs update. Reconcile the inventory. Then stop."},
    ]
    amb_dump = parse_cronlist_dump("0bbb2222 — Every hour (recurring) [session-only]: Docs update. Reconcile the…")
    ares = match_dump(amb_crons, amb_dump)
    ok(ares["missing"] == [] and len(ares["ambiguous"]) == 1, "ambiguous match is excluded from 'missing'")
    arep, _ = reconcile_report(amb_crons, amb_dump, rearm_all=False)
    ok("ARM (missing)" not in arep and "AMBIGUOUS" in arep, "ambiguous emits a warning, never an ARM")

    # (2) the empty sentinel is anchored — a prompt mentioning the phrase must not read as cold start
    notempty = parse_cronlist_dump("0ccc3333 — Hourly (recurring) [session-only]: Report if there are no scheduled jobs left…")
    ok(len(notempty) == 1, "'no scheduled jobs' inside a prompt still parses as an entry")
    ok(_EMPTY_DUMP_RE.search("No scheduled jobs.") is not None, "anchored sentinel matches the bare line")
    ok(_EMPTY_DUMP_RE.search("x — y [session-only]: no scheduled jobs here") is None, "sentinel does not match mid-line")

    # (3) --rearm-all deletes matched live copies, NOT true extras; then arms all
    rd_crons = [{"file": "1", "schedule": "1 * * * *", "purpose": "wd", "recurring": "true",
                 "target": "claude", "prompt": "Watchdog run. Then stop."}]
    rd_dump = parse_cronlist_dump(
        "0d000001 — Hourly (recurring) [session-only]: Watchdog run. Then…\n"
        "0e000002 — Hourly (recurring) [session-only]: Unmanaged extra job…")
    rrep, _ = reconcile_report(rd_crons, rd_dump, rearm_all=True)
    ok("CronDelete(id=0d000001)" in rrep, "rearm-all deletes the matched live copy")
    ok("CronDelete(id=0e000002)" not in rrep, "rearm-all does NOT delete a true extra")
    ok("ARM (missing): wd" in rrep, "rearm-all re-arms the manifest cron")

    # (4) the arm block emits the prompt flush-left between markers (copy-faithful, no phantom indent)
    ab = "\n".join(_arm_block({"schedule": "1 * * * *", "recurring": "true", "purpose": "p",
                               "prompt": "line one\nline two"}))
    ok(">>> BEGIN PROMPT\nline one\nline two\n>>> END PROMPT" in ab, "arm-block prompt is flush-left")

    # (5) en-dash and hyphen separators both parse
    ok(len(parse_cronlist_dump("0f000003 – Hourly (recurring) [session-only]: en-dash sep…")) == 1, "en-dash separator parses")

    if failures:
        print("self-test FAILED:")
        for f in failures:
            print("  - " + f)
        return 1
    print("self-test OK (%s)" % CONTRACT)
    return 0


# ── arg parsing + dispatch ───────────────────────────────────────────────────

VERBS = {
    "scaffold": cmd_scaffold,
    "render": cmd_render,
    "check": cmd_check,
    "reconcile": cmd_reconcile,
    "self-test": cmd_selftest,
}


def parse_args(argv: list[str]) -> tuple[str, dict]:
    if not argv:
        raise CronError("usage: crons {%s} [--root D] [--rearm-all]" % "|".join(VERBS))
    verb = argv[0]
    if verb in ("-h", "--help", "help"):
        print(__doc__)
        sys.exit(0)
    if verb not in VERBS:
        raise CronError("unknown verb %r (expected one of: %s)" % (verb, ", ".join(VERBS)))
    args: dict = {}
    rest = argv[1:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--root":
            if i + 1 >= len(rest):
                raise CronError("--root needs a directory")
            args["root"] = rest[i + 1]
            i += 2
        elif tok == "--rearm-all":
            args["rearm_all"] = True
            i += 1
        else:
            raise CronError("unexpected argument %r" % tok)
    return verb, args


def main(argv: list[str]) -> int:
    try:
        verb, args = parse_args(argv)
        return VERBS[verb](args)
    except CronError as e:
        print("crons: %s" % e, file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
