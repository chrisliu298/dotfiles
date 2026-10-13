#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""recall: search exact user/assistant turns in local Muse session transcripts.

The transcript store is read-only. Sessions live under
``${XDG_DATA_HOME:-~/.local/share}/muse/sessions/YYYY/MM/DD/<id>/session.jsonl``
as framed records; user turns are ``started`` run events with a ``prompt`` and
assistant turns are ``assistant_message_committed`` events with ``text``.
Unknown record kinds are skipped, never fatal. This build is self-contained:
the Muse copy-install contains only this directory, so nothing here may
require the sibling ``shared/`` tree (it is used opportunistically for the
per-file cache when present).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
    from file_cache import get_or_build
except Exception:  # installed Muse copy has no shared/ tree
    def get_or_build(path, source, version, builder):
        return builder()

PARSER_VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

LINE_CAP = 2_000_000
TEXT_CAP = 100_000
GIST_CAP = 360
CONFIRMATION_GIST_CAP = 160
DEFAULT_LIMIT = 5

_CJK = "ᄀ-ᇿ぀-ヿ㐀-䶿一-鿿가-힯豈-﫿"
_CJK_RE = re.compile(f"[{_CJK}]+")
_WORD_RE = re.compile(f"[A-Za-z0-9_./\\-]+|[{_CJK}]+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in", "on", "for",
    "with", "as", "is", "are", "was", "were", "be", "been", "do", "does", "did", "we", "i",
    "you", "it", "this", "that", "these", "those", "my", "our", "your", "me", "us", "what",
    "when", "how", "why", "where", "which", "about", "decide", "decided", "remember", "said",
    "mentioned", "earlier", "before", "thing", "things", "discuss", "discussed", "talk", "recall",
    "use", "using", "want", "wanted", "already", "settle", "settled", "agreed", "approach", "should",
    "would", "could", "can", "will", "lets", "let", "session", "history",
}

_TRIGGER_PHRASES = (
    "what did we decide about", "what did we decide on", "what did we decide",
    "what was our decision about", "what was the decision about", "what did we say about",
    "what we agreed on", "what we decided about", "remember when we", "remember that we",
    "as i mentioned earlier", "as i mentioned", "like i said before", "like i said",
    "as i said earlier", "as i said", "didn't we already", "didnt we already",
    "what was my preference for", "my preference for", "go back to what we",
    "as we discussed", "retrieve the context about", "find the session about",
)

# Pattern set shared with the Claude/Codex builds of recall.
_SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"), "openai-key"),
    (re.compile(r"\bxai-[A-Za-z0-9_\-]{12,}"), "xai-key"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), "github-token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws-key"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}", re.I), "bearer"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}"), "jwt"),
    (re.compile(r"(?i)[\"']?\b(?!(?:max_(?:new_)?tokens|tokenizer|token_count|token_limit|password_min_length|password_max_length)\b)[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|PLAN_KEY)[A-Z0-9_]*[\"']?\s*[:=]\s*[\"']?[^\s\"']+"), "env-secret"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"), "google-key"),
    (re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}"), "slack-token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "private-key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*\Z", re.S), "private-key"),
    (re.compile(r"data:[^;,\s]+;base64,[A-Za-z0-9+/=_\\-]{80,}"), "data-url"),
    (re.compile(r"(?<![A-Za-z0-9+/=_\\-])[A-Za-z0-9+/=_\\-]{500,}"), "long-blob"),
]


def redact(text: str) -> str:
    if not text:
        return text
    for pat, label in _SECRET_PATTERNS:
        text = pat.sub(f"[REDACTED:{label}]", text)
    return text


def _keep(t: str) -> bool:
    return t not in _STOPWORDS and (len(t) >= 2 or bool(_CJK_RE.fullmatch(t)))


def word_tokens(w: str) -> list[str]:
    if _CJK_RE.fullmatch(w):
        out = list(w) + [w[i:i + 2] for i in range(len(w) - 1)]
        if 1 < len(w) <= 8:
            out.append(w)
        return out
    wl = w.lower()
    out = [wl]
    for cam in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", w):
        cl = cam.lower()
        if cl != wl:
            out.append(cl)
    for part in re.split(r"[_./\-]+", wl):
        if part and part != wl:
            out.append(part)
    return out


def tokenize(text: str) -> list[str]:
    return [t for w in _WORD_RE.findall(text) for t in word_tokens(w) if _keep(t)]


def query_groups(cleaned: str) -> list[frozenset[str]]:
    groups = []
    for w in _WORD_RE.findall(cleaned):
        if _CJK_RE.fullmatch(w):
            grams = [w[i:i + 2] for i in range(len(w) - 1)] or [w]
            groups.extend(frozenset([g]) for g in grams)
            continue
        g = frozenset(t for t in word_tokens(w) if _keep(t))
        if g:
            groups.append(g)
    return list(dict.fromkeys(groups))


def normalize_query(q: str) -> tuple[str, list[str], list[frozenset[str]]]:
    ql = " " + q.lower().strip() + " "
    for ph in sorted(_TRIGGER_PHRASES, key=len, reverse=True):
        ql = ql.replace(" " + ph + " ", " ")
    cleaned = re.sub(r"\s+", " ", ql).strip()
    return cleaned, list(dict.fromkeys(tokenize(cleaned))), query_groups(cleaned)


@dataclass
class Stats:
    files_scanned: int = 0
    records_seen: int = 0
    messages_kept: int = 0
    malformed_records: int = 0
    oversized_records: int = 0
    redactions: int = 0

    def add(self, other: "Stats") -> None:
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(self, name) + getattr(other, name))

    def as_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass
class FileMeta:
    path: Path
    session_id: str
    cwd: str = ""
    thread_source: str = "user"
    git_branch: str = ""
    mtime: float = 0.0


@dataclass
class Turn:
    session_id: str
    path: Path
    line: int
    ordinal: int
    item_id: str
    timestamp: str
    role: str
    text: str
    cwd: str
    thread_source: str = "user"
    git_branch: str = ""
    mtime: float = 0.0
    tokens: list[str] = field(default_factory=list)
    score: float = 0.0
    coverage: float = 0.0
    matched: int = 0


def session_root() -> Path:
    override = os.environ.get("MUSE_RECALL_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")).expanduser()
    return (data / "muse" / "sessions").resolve()


def current_session_id(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    for name in ("MUSE_SESSION_ID", "MUSE_THREAD_ID"):
        if os.environ.get(name):
            return os.environ[name]
    log = os.environ.get("MUSE_CURRENT_SESSION_LOG")
    return Path(log).parent.name if log else ""


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _iso(recorded_at, fallback_mtime: float) -> str:
    if isinstance(recorded_at, (int, float)) and recorded_at > 0:
        moment = datetime.fromtimestamp(recorded_at / 1e6, timezone.utc)
    else:
        moment = datetime.fromtimestamp(fallback_mtime, timezone.utc)
    return moment.isoformat().replace("+00:00", "Z")


def _workspace_of(payload: dict, payload_type: str, event: dict) -> str | None:
    if payload_type == "runtime.session.metadata":
        value = payload.get("workspace_root")
        nested = payload.get("record")
        if not isinstance(value, str) and isinstance(nested, dict):
            value = nested.get("workspace_root")
        return value if isinstance(value, str) else None
    if payload_type == "runtime.session" and event.get("kind") == "context_projection_checkpoint":
        meta = event.get("session_metadata")
        if isinstance(meta, dict) and isinstance(meta.get("workspace_root"), str):
            return meta["workspace_root"]
    return None


def extract_turns(path: Path, *, include_non_human: bool = False) -> tuple[list[Turn], Stats]:
    stats = Stats(files_scanned=1)
    turns: list[Turn] = []
    session_id = path.parent.name
    mtime = safe_mtime(path)
    workspace = ""
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return turns, stats
    with handle:
        for lineno, line in enumerate(handle, 1):
            if len(line) > LINE_CAP:
                stats.oversized_records += 1
                continue
            try:
                record = json.loads(line)
            except ValueError:
                stats.malformed_records += 1
                continue
            if not isinstance(record, dict):
                stats.malformed_records += 1
                continue
            stats.records_seen += 1
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            event = payload.get("event")
            event = event if isinstance(event, dict) else {}
            workspace = _workspace_of(payload, str(record.get("payload_type") or ""), event) or workspace
            kind = str(event.get("kind") or payload.get("kind") or "")
            role = text = None
            if kind == "started" and payload.get("kind") == "run" and isinstance(event.get("prompt"), str):
                role, text = "user", event["prompt"]
            elif kind == "assistant_message_committed" and isinstance(event.get("text"), str):
                role, text = "assistant", event["text"]
            if not role or not text.strip():
                continue
            text = redact(text[:TEXT_CAP])
            sid = session_id  # directory name is the store's session identity
            seq = record.get("sequence")
            seq = seq if isinstance(seq, int) else lineno
            turns.append(Turn(
                session_id=sid, path=path, line=lineno, ordinal=seq,
                item_id=f"seq-{seq}", timestamp=_iso(record.get("recorded_at"), mtime),
                role=role, text=text, cwd=workspace, mtime=mtime,
            ))
    for turn in turns:  # workspace may be declared after the first turn
        turn.cwd = turn.cwd or workspace
    stats.messages_kept = len(turns)
    return turns, stats


def all_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    files = [p for p in root.rglob("session.jsonl")
             if p.is_file() and "subagent" not in p.relative_to(root).parts]
    return sorted(files, key=safe_mtime, reverse=True)


def read_file_meta(path: Path) -> FileMeta:
    cwd = ""
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if len(line) > LINE_CAP:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
                    continue
                payload = record["payload"]
                event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
                cwd = _workspace_of(payload, str(record.get("payload_type") or ""), event) or cwd
                if cwd:
                    break
    except OSError:
        pass
    return FileMeta(path=path, session_id=path.parent.name, cwd=cwd, mtime=safe_mtime(path))


def file_inventory(root: Path) -> list[FileMeta]:
    return [read_file_meta(p) for p in all_files(root)]


def files_for_scope(inventory: list[FileMeta], scope: str, *, cwd: str, session_id: str) -> list[FileMeta]:
    if scope == "current-task":
        return [m for m in inventory if session_id and m.session_id == session_id]
    if scope == "current-project":
        resolved = str(Path(cwd).expanduser().resolve())
        return [m for m in inventory if m.cwd and str(Path(m.cwd).expanduser().resolve()) == resolved]
    return list(inventory)


def load_turns(files, *, include_non_human: bool = False) -> tuple[list[Turn], Stats]:
    turns: list[Turn] = []
    total = Stats()
    for meta in files:
        path = meta.path if isinstance(meta, FileMeta) else Path(meta)
        found, stats = extract_turns(path, include_non_human=include_non_human)
        turns.extend(found)
        total.add(stats)
    turns.sort(key=lambda t: (t.session_id, t.timestamp, t.ordinal))
    return turns, total


def _collapse(text: str, cap: int = GIST_CAP) -> str:
    flat = re.sub(r"\s+", " ", redact(text)).strip()
    return flat if len(flat) <= cap else flat[:cap].rstrip() + "…"


def _local_date(turn: Turn) -> str:
    try:
        moment = datetime.fromisoformat(turn.timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        moment = datetime.fromtimestamp(turn.mtime)
    return moment.astimezone().date().isoformat()


def _relative_transcript(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def confirmation_line(turn: Turn) -> str:
    gist = _collapse(turn.text, CONFIRMATION_GIST_CAP)
    if turn.role != "user":
        gist = "agent turn, unconfirmed by user: " + gist
    return f"recall: {_local_date(turn)} · {turn.session_id[:8]} · {gist}"


def turn_kind(turn: Turn) -> str:
    return turn.role


def turn_json(turn: Turn, root: Path, rank: int) -> dict:
    return {
        "rank": rank,
        "score": round(turn.score, 3),
        "coverage": round(turn.coverage, 3),
        "matched_terms": turn.matched,
        "role": turn.role,
        "kind": turn_kind(turn),
        "timestamp": turn.timestamp,
        "excerpt": _collapse(turn.text),
        "confirmation": confirmation_line(turn),
        "locator": {
            "session_id": turn.session_id,
            "item_id": turn.item_id,
            "transcript": _relative_transcript(turn.path, root),
            "line": turn.line,
            "ordinal": turn.ordinal,
        },
        "cwd": turn.cwd,
        "git_branch": turn.git_branch,
        "attribution": (
            f"user turn in {turn.session_id[:8]} at L{turn.line}"
            if turn.role == "user"
            else f"assistant turn in {turn.session_id[:8]} at L{turn.line}; not user-confirmed"
        ),
    }


def rank_turns(turns: list[Turn], query: str, limit: int) -> tuple[str, list[Turn]]:
    cleaned, terms, groups = normalize_query(query)
    if not groups:
        return "empty_query", []
    counts = []
    lengths = []
    df: Counter = Counter()
    for turn in turns:
        counter = Counter(tokenize(turn.text))
        counts.append(counter)
        lengths.append(sum(counter.values()))
        df.update(counter.keys())
    average = sum(lengths) / max(1, len(lengths)) or 1
    scored = []
    for turn, counter, length in zip(turns, counts, lengths):
        matched = set()
        score = 0.0
        for term in terms:
            hits = counter.get(term, 0)
            if not hits:
                continue
            matched.add(term)
            weight = math.log(1 + (len(turns) - df[term] + .5) / (df[term] + .5))
            score += weight * hits * 2.5 / (hits + 1.5 * (.25 + .75 * length / average))
        coverage = sum(bool(g & matched) for g in groups) / max(1, len(groups))
        if coverage < .6:
            continue
        turn.score = score * coverage * (1.4 if turn.role == "user" else 1)
        turn.coverage = coverage
        turn.matched = len(matched)
        if cleaned and cleaned in turn.text.lower():
            turn.score *= 1.4
        scored.append(turn)
    scored.sort(key=lambda t: (-t.score, -t.coverage, t.session_id, t.ordinal))
    if not scored:
        return "no_match", []
    distinct = []
    seen_sessions = set()
    for turn in scored:
        if turn.session_id not in seen_sessions:
            distinct.append(turn)
            seen_sessions.add(turn.session_id)
    top = distinct[0]
    confident = top.coverage >= .6 and (
        len(distinct) == 1 or top.score >= 1.15 * max(distinct[1].score, 1e-9)
    )
    return ("confident" if confident else "ambiguous"), scored[:limit]


def search_history(root: Path, query: str, *, cwd: str = "", scope: str = "all",
                   explicit_session_id: str = "", roles: str = "both", limit: int = DEFAULT_LIMIT) -> dict:
    started = time.monotonic()
    inventory = file_inventory(root)
    current = current_session_id(explicit_session_id or None)
    effective_scope = "all" if scope in ("auto", "all") else scope
    files = files_for_scope(inventory, effective_scope, cwd=cwd, session_id=current)
    turns, stats = load_turns(files)
    excluded = None
    if effective_scope != "current-task" and current:
        excluded = current
        turns = [t for t in turns if t.session_id != current]
    if roles != "both":
        turns = [t for t in turns if t.role == roles]
    status, hits = rank_turns(turns, query, limit)
    candidates = [turn_json(turn, root, rank) for rank, turn in enumerate(hits, 1)]
    output = {"status": status, "candidates": candidates, "stats": stats.as_dict(),
              "excluded_current_task": excluded, "verification_required": bool(candidates),
              "elapsed_ms": round((time.monotonic() - started) * 1000)}
    if status == "confident" and candidates:
        output["confirmation"] = candidates[0]["confirmation"]
    return output


def show_context(root: Path, session_id: str, item_id: str, *, before: int, after: int,
                 max_chars: int, offset: int = 0) -> dict:
    max_chars = min(max(max_chars, 1000), 50000)
    inventory = file_inventory(root)
    exact = [m for m in inventory if m.session_id == session_id]
    matches = exact or [m for m in inventory if m.session_id.startswith(session_id)]
    session_ids = sorted({m.session_id for m in matches})
    if not matches:
        return {"status": "not_found", "reason": f"no session matches {session_id!r}"}
    if len(session_ids) > 1:
        return {"status": "ambiguous_session", "candidates": session_ids[:10]}
    turns, stats = load_turns(matches)
    turns = [t for t in turns if t.session_id == session_ids[0]]
    turns.sort(key=lambda t: t.ordinal)
    anchors = [i for i, t in enumerate(turns) if t.item_id == item_id] or [
        i for i, t in enumerate(turns) if t.item_id.startswith(item_id)]
    if not anchors:
        return {"status": "not_found", "reason": f"no item matches {item_id!r}", "stats": stats.as_dict()}
    if len(anchors) > 1:
        return {"status": "ambiguous_item", "candidates": [turns[i].item_id for i in anchors[:10]],
                "stats": stats.as_dict()}
    anchor = anchors[0]
    lo, hi = max(0, anchor - before), min(len(turns), anchor + after + 1)
    output = []
    remaining = max_chars
    for index in range(lo, hi):
        turn = turns[index]
        text = turn.text[offset:offset + remaining] if index == anchor else turn.text[:remaining]
        remaining -= len(text)
        output.append({"role": turn.role, "timestamp": turn.timestamp, "text": text,
                       "is_anchor": index == anchor,
                       "locator": {"session_id": turn.session_id, "item_id": turn.item_id,
                                   "transcript": _relative_transcript(turn.path, root),
                                   "line": turn.line, "ordinal": turn.ordinal}})
        if remaining <= 0:
            break
    return {"status": "ok", "session_id": session_ids[0], "anchor_item_id": turns[anchor].item_id,
            "anchor_offset": offset, "turns": output,
            "truncated": len(output) < hi - lo, "stats": stats.as_dict()}


def list_sessions(root: Path, *, cwd: str, scope: str, limit: int) -> dict:
    inventory = file_inventory(root)
    chosen = files_for_scope(inventory, scope, cwd=cwd, session_id=current_session_id())
    return {"status": "ok", "sessions": [
        {"session_id": m.session_id, "cwd": m.cwd, "transcript": _relative_transcript(m.path, root)}
        for m in chosen[:limit]]}


def doctor(root: Path, cwd: str) -> dict:
    inventory = file_inventory(root)
    return {"status": "ok", "root": str(root), "files": len(inventory),
            "current_session_id": current_session_id() or None, "cwd": cwd}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", type=Path, default=None, help=argparse.SUPPRESS)
    commands = result.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="search historical conversational turns")
    search.add_argument("--query", "-q", required=True)
    search.add_argument("--cwd", default=os.getcwd())
    search.add_argument("--scope", choices=("auto", "current-task", "current-project", "all"), default="auto")
    search.add_argument("--session-id", default="")
    search.add_argument("--roles", choices=("both", "user", "assistant"), default="both")
    search.add_argument("--limit", type=int, choices=range(1, 21), default=DEFAULT_LIMIT)
    show = commands.add_parser("show", help="show conversational turns around a search result")
    show.add_argument("--session-id", required=True)
    show.add_argument("--item-id", required=True)
    show.add_argument("--offset", type=int, default=0)
    show.add_argument("--before", type=int, choices=range(0, 21), default=3)
    show.add_argument("--after", type=int, choices=range(0, 21), default=5)
    show.add_argument("--max-chars", type=int, default=12000)
    sessions = commands.add_parser("sessions", help="list candidate Muse sessions")
    sessions.add_argument("--cwd", default=os.getcwd())
    sessions.add_argument("--scope", choices=("current-task", "current-project", "all"), default="current-project")
    sessions.add_argument("--limit", type=int, choices=range(1, 101), default=20)
    diagnose = commands.add_parser("doctor", help="inspect transcript discovery")
    diagnose.add_argument("--cwd", default=os.getcwd())
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = (args.root or session_root()).expanduser().resolve()
    if args.command == "search":
        output = search_history(root, args.query, cwd=args.cwd, scope=args.scope,
                                explicit_session_id=args.session_id, roles=args.roles, limit=args.limit)
    elif args.command == "show":
        output = show_context(root, args.session_id, args.item_id, before=args.before,
                              after=args.after, max_chars=args.max_chars, offset=args.offset)
    elif args.command == "sessions":
        output = list_sessions(root, cwd=args.cwd, scope=args.scope, limit=args.limit)
    else:
        output = doctor(root, args.cwd)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 1 if output.get("status") in ("error", "not_found", "ambiguous_session", "ambiguous_item") else 0


if __name__ == "__main__":
    raise SystemExit(main())


