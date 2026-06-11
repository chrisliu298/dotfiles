#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""rehydrate.py — recover post-compaction context from the *current* session's raw transcript.

The harness compacted the session: it replaced the raw history with a lossy summary and
continued. The raw transcript is still on disk. This script locates it, finds the compaction
boundary, and emits a small structured "continuity capsule" of the detail the summary dropped
(decisions, file paths, errors, user corrections, open threads). The agent reads the capsule —
never the raw JSONL (re-reading it re-overflows the window, which is the whole problem).

Subcommands:
  locate   find the current session transcript + compaction boundary           -> JSON
  digest   broad structured recovery capsule, char-budgeted                    -> Markdown
  query    targeted search over the pre-boundary raw records                   -> Markdown
  doctor   diagnostics: candidate sessions and why one was / wasn't picked     -> text

Run with uv (zero deps, stdlib only):
  uv run ~/dotfiles/agents/extensions/skills/rehydrate/scripts/rehydrate.py digest --cwd "$PWD"

Design notes live in references/{claude,codex,grok,schema}.md. Detection is STRUCTURAL
(record type/subtype/flag), never a lexical grep for "compact" — that has ~0% precision
because the word appears in ordinary task text.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

HOME = Path.home()
DEFAULT_MAX_CHARS = 14000          # ~3.5k tokens at ~4 chars/token (user default: ~3-4k)
PER_EVENT_TEXT_CAP = 1600          # truncate any single event's text before it enters a bucket
HUGE_LINE = 2_000_000              # bytes; above this, peek the record type, don't full-parse
RECENT_DAYS = 8                    # Codex rollout lookback window (days)
MAX_CODEX_SCAN = 500               # cap rollouts inspected per locate (newest-first within window)

# ---------------------------------------------------------------------------- redaction
_SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"), "openai-key"),
    (re.compile(r"\bxai-[A-Za-z0-9_\-]{12,}"), "xai-key"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), "github-token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws-key"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}"), "bearer"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}"), "jwt"),
    (re.compile(r"(?i)\b[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|PLAN_KEY)\s*=\s*[^\s\"']+"), "env-secret"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private-key"),
]
_redaction_count = 0


def redact(text: str) -> str:
    global _redaction_count
    if not text:
        return text
    for pat, label in _SECRET_PATTERNS:
        text, n = pat.subn(f"[REDACTED:{label}]", text)
        _redaction_count += n
    return text


# ---------------------------------------------------------------------------- data model
@dataclass
class Event:
    line: int
    role: str            # user | assistant | tool | system | meta
    kind: str            # user_message | assistant_message | file_op | command | command_output
    text: str = ""       # already truncated/redacted snippet
    paths: list[str] = field(default_factory=list)
    command: str | None = None
    exit_code: int | None = None
    sidechain: bool = False


@dataclass
class Boundary:
    line: int | None     # 1-based cutoff line, or None when the whole file is in scope (Grok)
    kind: str            # the structural marker that proved compaction


@dataclass
class SessionRef:
    harness: str
    transcript: Path
    session_id: str | None
    cwd: str
    confidence: str = "high"
    warnings: list[str] = field(default_factory=list)


class Ambiguous(Exception):
    def __init__(self, candidates):
        self.candidates = candidates


class NotFound(Exception):
    pass


# ---------------------------------------------------------------------------- helpers
def realpath(p: str) -> str:
    return os.path.realpath(os.path.expanduser(p))


def same_path(a: str, b: str) -> bool:
    return a == b or realpath(a) == realpath(b)


def safe_mtime(p) -> float:
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0.0


def _to_epoch(v) -> float:
    """Normalize a summary.json updated_at (ISO string) or an mtime float to a sortable epoch."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def peek_type(head: str) -> str | None:
    m = re.search(r'"type"\s*:\s*"([^"]+)"', head[:600])
    return m.group(1) if m else None


def iter_lines(path: Path):
    """Yield (line_no, raw_record_or_None, head_str), 1-based by physical line.

    Bounded read: readline(HUGE_LINE+1) never pulls more than the cap into memory, so a
    multi-hundred-MB Codex `replacement_history` line is peeked (head only) and drained,
    never fully parsed. A vanished/locked file is skipped rather than crashing the run.
    """
    try:
        fh = path.open("r", errors="replace")
    except OSError:
        return
    with fh:
        i = 0
        while True:
            try:
                chunk = fh.readline(HUGE_LINE + 1)
            except OSError:
                return
            if not chunk:
                break
            i += 1
            if len(chunk) > HUGE_LINE and not chunk.endswith("\n"):
                head = chunk[:600]
                while True:                       # drain the rest of this physical line
                    more = fh.readline(HUGE_LINE)
                    if not more or more.endswith("\n"):
                        break
                yield i, None, head
                continue
            line = chunk.rstrip("\n")
            if not line.strip():
                continue
            try:
                yield i, json.loads(line), line[:600]
            except json.JSONDecodeError:
                yield i, None, line[:600]


def clip(text, cap=PER_EVENT_TEXT_CAP):
    # Redact BEFORE any whitespace-collapse/truncation, so a secret can't survive by being
    # split across a clip boundary or pushed off a line anchor. Every emitted snippet flows
    # through clip(), so this is the single choke point for redaction of text and commands.
    text = redact((text or "").strip())
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= cap else text[:cap] + " …"


def pid_ancestry():
    """Walk parent PIDs via ps so we can match a live session by its process tree."""
    pids, pid = [], os.getppid()
    for _ in range(12):
        if pid <= 1:
            break
        pids.append(pid)
        try:
            out = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)],
                                 capture_output=True, text=True, timeout=2)
            pid = int(out.stdout.strip() or 0)
        except Exception:
            break
    return pids


# ---------------------------------------------------------------------------- Claude adapter
class Claude:
    name = "claude"

    @staticmethod
    def detect() -> bool:
        return bool(os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_SESSION_ID"))

    @staticmethod
    def recognizes(rec) -> bool:
        return rec.get("type") in ("user", "assistant", "system")

    @staticmethod
    def encode_cwd(cwd: str) -> str:
        return cwd.replace("/", "-").replace(".", "-")

    @classmethod
    def candidates(cls, cwd):
        proj = HOME / ".claude" / "projects" / cls.encode_cwd(cwd)
        files = sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if proj.is_dir() else []
        return proj, files

    @classmethod
    def locate(cls, cwd) -> SessionRef:
        proj, files = cls.candidates(cwd)
        if not files:
            raise NotFound(f"no Claude transcripts under {proj}")
        warnings = []
        # 1) env session id (most reliable)
        sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
        if sid and (proj / f"{sid}.jsonl").exists():
            return SessionRef("claude", proj / f"{sid}.jsonl", sid, cwd, "high")
        # 2) live PID map: ~/.claude/sessions/<pid>.json  {pid, sessionId, cwd, status}
        ancestry = set(pid_ancestry())
        sess = []
        for j in (HOME / ".claude" / "sessions").glob("*.json"):
            try:
                d = json.loads(j.read_text())
            except Exception:
                continue
            if d.get("cwd") and same_path(d["cwd"], cwd) and (proj / f"{d.get('sessionId')}.jsonl").exists():
                sess.append((d, j.stat().st_mtime))
        live = [d for d, _ in sorted(sess, key=lambda x: x[1], reverse=True) if d.get("pid") in ancestry]
        chosen = (live or [d for d, _ in sorted(sess, key=lambda x: x[1], reverse=True)])
        if chosen:
            d = chosen[0]
            return SessionRef("claude", proj / f"{d['sessionId']}.jsonl", d["sessionId"], cwd,
                              "high" if live else "medium",
                              [] if live else ["session matched by recency, not live PID"])
        # 3) mtime fallback
        warnings.append("no session-id/PID match; picked newest transcript by mtime (low confidence)")
        return SessionRef("claude", files[0], files[0].stem, cwd, "low", warnings)

    @staticmethod
    def find_boundary(path) -> Boundary | None:
        last = None
        for ln, rec, head in iter_lines(path):
            if rec is None:
                continue
            t, st = rec.get("type"), rec.get("subtype")
            if t == "system" and st in ("compact_boundary", "away_summary"):
                last = Boundary(ln, f"system/{st}")
            elif t == "user" and rec.get("isCompactSummary") is True:
                last = Boundary(ln, "isCompactSummary")
        return last

    @staticmethod
    def events(path, up_to_line):
        for ln, rec, head in iter_lines(path):
            if rec is None or (up_to_line is not None and ln >= up_to_line):
                continue
            t = rec.get("type")
            if t not in ("user", "assistant"):
                continue
            sc = bool(rec.get("isSidechain"))
            msg = rec.get("message") or {}
            content = msg.get("content")
            text_parts, tool_out, paths, command = [], [], [], None
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    bt = b.get("type")
                    if bt == "text":
                        text_parts.append(b.get("text", ""))
                    elif bt == "tool_use":
                        inp = b.get("input") or {}
                        for k in ("file_path", "path", "notebook_path"):
                            if inp.get(k):
                                paths.append(inp[k])
                        if b.get("name") == "Bash" and inp.get("command"):
                            command = inp["command"]
                    elif bt == "tool_result":
                        rc = b.get("content")
                        if isinstance(rc, list):
                            rc = " ".join(x.get("text", "") for x in rc if isinstance(x, dict))
                        if isinstance(rc, str) and rc:
                            tool_out.append(rc)
            # A type:"user" record carrying tool_result blocks is a TOOL OUTPUT turn, not a
            # genuine user message — keep them apart so corrections/threads stay clean.
            if t == "assistant":
                if command:
                    yield Event(ln, "assistant", "command", clip(" ".join(text_parts)), paths,
                                clip(command, 400), None, sc)
                elif paths:
                    yield Event(ln, "assistant", "file_op", clip(" ".join(text_parts)), paths, None, None, sc)
                elif any(text_parts):
                    yield Event(ln, "assistant", "assistant_message", clip(" ".join(text_parts)), sidechain=sc)
            else:  # user record
                if tool_out and not any(p.strip() for p in text_parts):
                    yield Event(ln, "tool", "command_output", clip(" ".join(tool_out)), sidechain=sc)
                elif any(text_parts):
                    yield Event(ln, "user", "user_message", clip(" ".join(text_parts)), sidechain=sc)


# ---------------------------------------------------------------------------- Codex adapter
class Codex:
    name = "codex"

    @staticmethod
    def detect() -> bool:
        # No documented session-id env; detect by the explicit Codex marker vars when present.
        return bool(os.environ.get("CODEX_HOME") or os.environ.get("CODEX_SANDBOX")
                    or os.environ.get("CODEX_SESSION_ID"))

    @staticmethod
    def recognizes(rec) -> bool:
        return rec.get("type") in ("session_meta", "response_item", "event_msg", "turn_context", "compacted")

    @staticmethod
    def root():
        return Path(os.environ.get("CODEX_HOME", HOME / ".codex"))

    @classmethod
    def rollouts(cls):
        files = glob.glob(str(cls.root() / "sessions" / "*" / "*" / "*" / "rollout-*.jsonl"))
        cutoff = time.time() - RECENT_DAYS * 86400          # time-window, not a blind file-count cap
        recent = [f for f in files if safe_mtime(f) >= cutoff]
        return sorted(recent, key=safe_mtime, reverse=True)

    @classmethod
    def meta_cwd(cls, path) -> str | None:
        for ln, rec, head in iter_lines(Path(path)):
            if rec and rec.get("type") == "session_meta":
                return (rec.get("payload") or {}).get("cwd")
            return None  # session_meta is line 1; stop after first record
        return None

    @classmethod
    def locate(cls, cwd) -> SessionRef:
        matches = [p for p in cls.rollouts()[:MAX_CODEX_SCAN]
                   if (mcwd := cls.meta_cwd(p)) and same_path(mcwd, cwd)]
        if not matches:
            raise NotFound(f"no Codex rollout (within {RECENT_DAYS}d) with session_meta.cwd == {cwd}")
        # Ambiguity across the WHOLE matched set, not just the top two: if >=2 cwd-matched
        # rollouts were touched within 120s of the newest, we can't tell which is live.
        ranked = sorted(matches, key=safe_mtime, reverse=True)
        newest = safe_mtime(ranked[0])
        close = [p for p in ranked if newest - safe_mtime(p) < 120]
        if len(close) >= 2:
            raise Ambiguous(close[:5])
        warnings = [] if len(ranked) == 1 else [f"{len(ranked)} same-cwd rollouts in window; picked newest"]
        sid = re.search(r"rollout-[0-9T\-]+-([0-9a-f\-]+)\.jsonl", os.path.basename(ranked[0]))
        return SessionRef("codex", Path(ranked[0]), sid.group(1) if sid else None, cwd, "medium", warnings)

    @staticmethod
    def find_boundary(path) -> Boundary | None:
        last = None
        for ln, rec, head in iter_lines(path):
            t = rec.get("type") if rec else peek_type(head)
            if t == "compacted":
                last = Boundary(ln, "compacted")
        return last

    @staticmethod
    def events(path, up_to_line):
        for ln, rec, head in iter_lines(path):
            if rec is None or (up_to_line is not None and ln >= up_to_line):
                continue
            if rec.get("type") != "response_item":
                continue
            pl = rec.get("payload") or {}
            pt = pl.get("type")
            if pt in ("message",):
                role = pl.get("role", "assistant")
                content = pl.get("content")
                txt = content if isinstance(content, str) else " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict)) if isinstance(content, list) else ""
                yield Event(ln, role, "user_message" if role == "user" else "assistant_message", clip(txt))
            elif pt == "agent_message":
                yield Event(ln, "assistant", "assistant_message", clip(pl.get("message", "")))
            elif pt == "function_call":
                name = pl.get("name", "")
                args = pl.get("arguments", "")
                paths = re.findall(r'"(?:file_path|path)"\s*:\s*"([^"]+)"', args if isinstance(args, str) else "")
                cmd = None
                m = re.search(r'"command"\s*:\s*("(?:[^"\\]|\\.)*"|\[[^\]]*\])', args if isinstance(args, str) else "")
                if m:
                    cmd = m.group(1)
                yield Event(ln, "tool", "command" if cmd else "file_op", clip(name, 200),
                            paths, clip(cmd, 400) if cmd else None)
            elif pt == "function_call_output":
                out = pl.get("output")
                if isinstance(out, dict):
                    out = out.get("content") or json.dumps(out)[:PER_EVENT_TEXT_CAP]
                yield Event(ln, "tool", "command_output", clip(out if isinstance(out, str) else ""))


# ---------------------------------------------------------------------------- Grok adapter
class Grok:
    name = "grok"

    @staticmethod
    def detect() -> bool:
        return bool(os.environ.get("GROK_SESSION_ID") or os.environ.get("GROK_WORKSPACE_ROOT"))

    @staticmethod
    def recognizes(rec) -> bool:
        return rec.get("method") == "session/update" or bool((rec.get("params") or {}).get("update"))

    @staticmethod
    def root():
        return Path(os.environ.get("GROK_HOME", HOME / ".grok"))

    @classmethod
    def group_dir(cls, cwd):
        sessions = cls.root() / "sessions"
        enc = urllib.parse.quote(cwd, safe="")
        g = sessions / enc
        if g.is_dir():
            return g
        # long-path fallback: scan for a .cwd sidecar that names this cwd
        for cand in sessions.glob("*"):
            cwdf = cand / ".cwd"
            if cwdf.is_file() and same_path(cwdf.read_text().strip(), cwd):
                return cand
        return g  # may not exist; caller handles

    @classmethod
    def locate(cls, cwd) -> SessionRef:
        env_sid = os.environ.get("GROK_SESSION_ID")
        group = cls.group_dir(cwd)
        if not group.is_dir():
            raise NotFound(f"no Grok session group for {cwd} under {cls.root()/'sessions'}")
        scored = []
        for sdir in group.iterdir():
            if not sdir.is_dir():
                continue
            if env_sid and sdir.name == env_sid:
                return SessionRef("grok", sdir / "updates.jsonl", env_sid, cwd, "high")
            sj = sdir / "summary.json"
            updated = sdir.stat().st_mtime
            info_cwd = None
            if sj.is_file():
                try:
                    d = json.loads(sj.read_text())
                    updated = d.get("updated_at") or updated
                    info_cwd = (d.get("info") or {}).get("cwd")
                except Exception:
                    pass
            if info_cwd and not same_path(info_cwd, cwd):
                continue
            scored.append((updated, sdir))
        if not scored:
            raise NotFound(f"no Grok session dirs under {group}")
        scored.sort(key=lambda x: _to_epoch(x[0]), reverse=True)
        sdir = scored[0][1]
        return SessionRef("grok", sdir / "updates.jsonl", sdir.name, cwd,
                          "high" if env_sid else "medium",
                          [] if env_sid else ["session matched by summary.json updated_at, not GROK_SESSION_ID"])

    @staticmethod
    def find_boundary(path) -> Boundary | None:
        # updates.jsonl retains the FULL history (pre- AND post-compaction) and carries no
        # in-stream boundary line — so we can detect *that* compaction happened, not a cutoff.
        # line=None ⇒ scan the whole file; the kind string carries the honest caveat.
        sdir = path.parent
        caveat = " (no line cutoff — capsule may include post-compaction turns)"
        try:
            sig = json.loads((sdir / "signals.json").read_text())
            if int(sig.get("compactionCount", 0)) > 0:
                return Boundary(None, f"signals.compactionCount={sig['compactionCount']}{caveat}")
        except Exception:
            pass
        try:
            ckpt = sdir / "compaction_checkpoints"
            if ckpt.is_dir() and any(ckpt.iterdir()):
                return Boundary(None, f"compaction_checkpoints present{caveat}")
        except OSError:
            pass
        return None

    @staticmethod
    def events(path, up_to_line):
        for ln, rec, head in iter_lines(path):
            if rec is None or (up_to_line is not None and ln >= up_to_line):
                continue
            params = rec.get("params") or {}
            upd = params.get("update") or {}
            su = upd.get("sessionUpdate")
            if su == "user_message_chunk":
                yield Event(ln, "user", "user_message", clip(_grok_text(upd)))
            elif su == "agent_message_chunk":
                yield Event(ln, "assistant", "assistant_message", clip(_grok_text(upd)))
            elif su in ("tool_call", "tool_call_update"):
                title = upd.get("title") or upd.get("kind") or ""
                paths = re.findall(r"(/[^\s\"']+|[\w./\-]+\.\w+)", json.dumps(upd.get("locations", "")))
                yield Event(ln, "tool", "file_op" if paths else "command", clip(title, 200), paths[:4])
            # agent_thought_chunk / available_commands_update / plan → dropped or low-value


def _grok_text(update: dict) -> str:
    c = update.get("content")
    if isinstance(c, dict):
        return c.get("text", "")
    if isinstance(c, str):
        return c
    return update.get("text", "")


ADAPTERS = {"claude": Claude, "codex": Codex, "grok": Grok}


def detect_harness() -> str | None:
    for name, ad in ADAPTERS.items():
        if ad.detect():
            return name
    return None


def format_ok(ad, path, sample=200) -> bool:
    """True if any of the first `sample` records is one the adapter recognizes. A wholesale
    format change (harness renamed its record types) makes this False → drift warning."""
    n = 0
    for ln, rec, head in iter_lines(path):
        n += 1
        if rec is not None and ad.recognizes(rec):
            return True
        if n >= sample:
            break
    return False


def resolve(harness, cwd):
    if harness == "auto":
        harness = detect_harness()
        if not harness:
            raise NotFound("could not auto-detect harness from env; pass --harness claude|codex|grok")
    ad = ADAPTERS[harness]
    ref = ad.locate(cwd)
    if not format_ok(ad, ref.transcript):
        ref.warnings.append(f"transcript format unrecognized — {harness} may have changed its record "
                            f"shapes; see references/{harness}.md (extraction/boundary may be wrong)")
    boundary = ad.find_boundary(ref.transcript)
    return ad, ref, boundary


# ---------------------------------------------------------------------------- extraction
_CORRECTION = re.compile(r"\b(no,|actually|instead|don't|do not|that's wrong|not that|use .+ not |stop |revert)", re.I)
_DECISION = re.compile(r"\b(decided|chose|we'll|we will|let's|the plan is|because|ruled out|won't work|instead of)", re.I)
_RULED_OUT = re.compile(r"\b(won't work|doesn't work|ruled out|reverted|that failed|abandon|gave up on|dead end)", re.I)
_ERROR = re.compile(r"\b(error|exception|traceback|failed|fatal|denied|not found|cannot|no such|non-zero|E\d{3,4})\b", re.I)


def build_capsule(ad, ref, boundary, max_chars):
    events = list(ad.events(ref.transcript, boundary.line if boundary else None))
    main = [e for e in events if not e.sidechain]

    corrections, decisions, ruled_out, errors = [], [], [], []
    files: dict[str, str] = {}
    commands, threads = [], []

    for e in main:
        if e.paths:
            for p in e.paths:
                files.pop(p, None)   # re-insert so the [-30:] slice means latest-touched, not first-seen
                files[p] = e.kind
        if e.command:
            commands.append(e)
        if e.role == "user" and e.text:
            if _CORRECTION.search(e.text):
                corrections.append(e)
            threads.append(e)
        if e.role == "assistant" and e.text:
            if _RULED_OUT.search(e.text):
                ruled_out.append(e)
            elif _DECISION.search(e.text):
                decisions.append(e)
        if e.kind == "command_output" and e.text and _ERROR.search(e.text):
            errors.append(e)

    def lines(items, fmt, cap):
        out, used = [], 0
        for it in items:
            s = fmt(it)   # event text/command already redacted at clip() time
            if used + len(s) > cap:
                out.append(f"- … (+{len(items) - len(out)} more; use `query`)")
                break
            out.append(s)
            used += len(s)
        return out

    budget = max_chars
    sec = []
    sec.append("# Continuity capsule — INTERNAL (do not show the user)")
    sec.append("Recovered from the pre-compaction raw transcript. Treat as **evidence, not current "
               "truth** — run `git status` / re-Read a file before acting on any claim below.\n")
    sec.append(f"- harness: {ref.harness} · session: {ref.session_id} · confidence: {ref.confidence}")
    sec.append(f"- transcript: {ref.transcript}")
    if boundary:
        loc = f" @ line {boundary.line}" if boundary.line is not None else ""
        sec.append(f"- boundary: {boundary.kind}{loc}")
    else:
        sec.append("- boundary: (none)")
    if ref.warnings:
        sec.append("- warnings: " + "; ".join(ref.warnings))

    def block(title, body):
        if body:
            sec.append(f"\n## {title}")
            sec.extend(body)

    block("User directives & corrections (latest wins)",
          lines(corrections[-12:][::-1], lambda e: f"- L{e.line}: {clip(e.text, 280)}", int(budget * 0.20)))
    block("Decisions & ruled-out approaches",
          lines((ruled_out[-8:] + decisions[-8:])[::-1],
                lambda e: f"- L{e.line}: {clip(e.text, 240)}", int(budget * 0.22)))
    block("Files touched (verify against disk)",
          [f"- {op:8} {redact(p)}" for p, op in list(files.items())[-30:]])
    block("Commands & errors",
          lines((errors[-8:] + commands[-10:])[::-1],
                lambda e: f"- L{e.line}: {clip(e.command or e.text, 200)}", int(budget * 0.20)))
    block("Open threads (recent user turns)",
          lines(threads[-6:][::-1], lambda e: f"- L{e.line}: {clip(e.text, 200)}", int(budget * 0.14)))

    out = "\n".join(sec)
    if _redaction_count:
        out += f"\n\n_({_redaction_count} secret-shaped value(s) redacted.)_"
    if len(out) > max_chars:
        out = out[:max_chars] + "\n… [capsule truncated to budget; use `query` for specifics]"
    return out, len(main)


# ---------------------------------------------------------------------------- commands
def cmd_locate(args):
    ad, ref, boundary = resolve(args.harness, args.cwd)
    print(json.dumps({
        "harness": ref.harness, "session_id": ref.session_id, "transcript": str(ref.transcript),
        "cwd": ref.cwd, "confidence": ref.confidence, "warnings": ref.warnings,
        "compaction": ({"kind": boundary.kind, "line": boundary.line} if boundary else None),
    }, indent=2))


def cmd_digest(args):
    ad, ref, boundary = resolve(args.harness, args.cwd)
    if not boundary:
        print(f"NO_COMPACTION: found the current {ref.harness} session ({ref.transcript}) but no "
              f"compaction boundary — nothing to rehydrate; the context you have is the full history. "
              f"(If you KNOW this session was compacted, the boundary marker may have drifted — run "
              f"`doctor` and check references/{ref.harness}.md.)")
        return 13
    out, n = build_capsule(ad, ref, boundary, args.max_chars)
    print(out)
    print(f"\n<!-- scanned {n} pre-boundary records · {len(out)} chars -->", file=sys.stderr)


def cmd_query(args):
    ad, ref, boundary = resolve(args.harness, args.cwd)
    terms = [t.lower() for t in args.q.split() if len(t) > 2] or [args.q.strip().lower()]
    evs = list(ad.events(ref.transcript, boundary.line if boundary else None))
    hits = [e for e in evs if e.text and all(t in e.text.lower() for t in terms)] or \
           [e for e in evs if e.text and any(t in e.text.lower() for t in terms)]
    print(f"# Targeted recovery: {redact(args.q)}\n")
    if not hits:
        print("No matching pre-boundary records. Try fewer/broader terms.")
        return
    used = 0
    for e in hits[-args.k:][::-1]:
        s = f"- L{e.line} ({e.kind}): {clip(e.text, 360)}\n"   # clip() redacts
        if used + len(s) > args.max_chars:
            break
        print(s, end="")
        used += len(s)


def cmd_doctor(args):
    harness = args.harness if args.harness != "auto" else (detect_harness() or "?")
    print(f"detected harness: {harness}")
    print(f"env: CLAUDECODE={os.environ.get('CLAUDECODE')} "
          f"CLAUDE_CODE_SESSION_ID={os.environ.get('CLAUDE_CODE_SESSION_ID')} "
          f"CODEX_HOME={os.environ.get('CODEX_HOME')} GROK_SESSION_ID={os.environ.get('GROK_SESSION_ID')}")
    cwd = args.cwd
    if harness == "claude":
        proj, files = Claude.candidates(cwd)
        print(f"project dir: {proj} (exists={proj.is_dir()})")
        for f in files[:args.show_candidates]:
            print(f"  {f.name}  mtime={int(f.stat().st_mtime)}  boundary={Claude.find_boundary(f)}")
    elif harness == "codex":
        for p in Codex.rollouts()[:args.show_candidates]:
            print(f"  {os.path.basename(p)}  cwd={Codex.meta_cwd(p)}  mtime={int(os.path.getmtime(p))}")
    elif harness == "grok":
        g = Grok.group_dir(cwd)
        print(f"group dir: {g} (exists={g.is_dir()})")
        if g.is_dir():
            for d in list(g.iterdir())[:args.show_candidates]:
                print(f"  {d.name}  boundary={Grok.find_boundary(d/'updates.jsonl') if (d/'updates.jsonl').exists() else 'no-updates'}")
    try:
        ad, ref, boundary = resolve(args.harness, cwd)
        print(f"\nRESOLVED: {ref.transcript}  confidence={ref.confidence}  boundary={boundary}")
    except (NotFound, Ambiguous) as e:
        print(f"\nRESOLVE FAILED: {type(e).__name__}: {e}")


def main():
    p = argparse.ArgumentParser(prog="rehydrate", description=__doc__.splitlines()[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--harness", default="auto", choices=["auto", "claude", "codex", "grok"])
    common.add_argument("--cwd", default=os.getcwd())
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("locate", parents=[common])
    d = sub.add_parser("digest", parents=[common]); d.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    q = sub.add_parser("query", parents=[common]); q.add_argument("--q", required=True); q.add_argument("--k", type=int, default=8)
    q.add_argument("--max-chars", type=int, default=4000)
    dr = sub.add_parser("doctor", parents=[common]); dr.add_argument("--show-candidates", type=int, default=10)
    args = p.parse_args()
    args.cwd = os.path.abspath(os.path.expanduser(args.cwd))
    try:
        rc = {"locate": cmd_locate, "digest": cmd_digest, "query": cmd_query, "doctor": cmd_doctor}[args.cmd](args)
        sys.exit(rc or 0)
    except Ambiguous as e:
        print("AMBIGUOUS: multiple current-cwd sessions match (not guessing). Candidates:", file=sys.stderr)
        for c in e.candidates:
            print(f"  {c}", file=sys.stderr)
        print("Re-run with --harness and inspect with `doctor`, or pass the right one explicitly.", file=sys.stderr)
        sys.exit(12)
    except NotFound as e:
        print(f"NOT_FOUND: {e}", file=sys.stderr)
        sys.exit(11)
    except OSError as e:
        print(f"IO_ERROR: {e} (a transcript may have been rotated mid-read; retry)", file=sys.stderr)
        sys.exit(14)


if __name__ == "__main__":
    main()
