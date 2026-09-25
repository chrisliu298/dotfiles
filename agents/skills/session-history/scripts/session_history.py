#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Search exact user/assistant turns in local Codex rollout transcripts.

The transcript store is read-only. Search is intentionally stateless: narrower
current-task/project scopes are tried before the full history, and no persistent
content index or background service is created.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator


LINE_CAP = 2_000_000
TEXT_CAP = 100_000
GIST_CAP = 360
DEFAULT_LIMIT = 5
BM25_K1 = 1.5
BM25_B = 0.75
CANDIDATE_COVERAGE = 0.4
CONFIDENT_COVERAGE = 0.6
CONFIDENT_MARGIN = 1.15
USER_BOOST = 1.6
CUE_BOOST = 1.25
PHRASE_BOOST = 1.4
RECENCY_BOOST = 0.15

_CJK_RE = re.compile(r"[\u1100-\u11ff\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff]+")
_WORD_RE = re.compile(r"[A-Za-z0-9_./\-]+|[\u1100-\u11ff\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff]+")
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

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

_CUE = re.compile(
    r"\b(decided|chose|choose|we'll|we will|let's|lets|the plan is|because|ruled out|"
    r"won't work|wont work|instead|actually|don't|do not|prefer|preference|revert|"
    r"default to|agreed|settled on)\b",
    re.I,
)

_INJECTED_PREFIXES = (
    "<recommended_plugins>", "# agents.md instructions for", "<environment_context>",
    "<skill>", "<skills_instructions>", "<app-context>", "<permissions instructions>",
    "<collaboration_mode>", "<multi_agent_mode>", "<heartbeat>", "<image",
    "<in-app-browser-context", "<turn_aborted", "<user_instructions", "<codex_internal_context",
    "<codex_delegation", "<subagent_notification", "<send_user_message_question_reply", "</image>",
    "# files mentioned by the user:", "## referenced chats with codex:",
)

_NON_HUMAN_SOURCES = ("subagent", "automation", "headless", "exec", "inter_agent", "inter-agent")

_SECRET_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"), "openai-key"),
    (re.compile(r"\bxai-[A-Za-z0-9_\-]{12,}"), "xai-key"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), "github-token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws-key"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}", re.I), "bearer"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}"), "jwt"),
    (re.compile(r"(?i)[\"']?\b[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|PLAN_KEY)[A-Z0-9_]*[\"']?\s*[:=]\s*[\"']?[^\s\"']+"), "env-secret"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"), "google-key"),
    (re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}"), "slack-token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "private-key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private-key"),
    (re.compile(r"data:[^;,\s]+;base64,[A-Za-z0-9+/=_\-]{80,}"), "data-url"),
    (re.compile(r"(?<![A-Za-z0-9+/=_\-])[A-Za-z0-9+/=_\-]{500,}"), "long-blob"),
)


@dataclass
class Stats:
    files_scanned: int = 0
    records_seen: int = 0
    messages_kept: int = 0
    malformed_records: int = 0
    oversized_records: int = 0
    injected_parts_skipped: int = 0
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
    thread_source: str = ""
    originator: str = ""
    git_branch: str = ""
    started_at: str = ""
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
    thread_source: str
    git_branch: str
    mtime: float
    tokens: list[str] = field(default_factory=list)
    score: float = 0.0
    coverage: float = 0.0
    matched: int = 0


def session_root() -> Path:
    override = os.environ.get("CODEX_SESSION_HISTORY_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return (codex_home / "sessions").resolve()


def current_session_id(explicit: str | None = None) -> str:
    return explicit or os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID") or ""


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _fallback_session_id(path: Path) -> str:
    ids = _UUID_RE.findall(path.stem)
    return ids[0] if ids else path.stem


def iter_bounded_lines(path: Path) -> Iterator[tuple[int, bytes | None]]:
    """Yield physical 1-based lines without loading huge records into memory."""
    try:
        fh = path.open("rb")
    except OSError:
        return
    with fh:
        line_no = 0
        while True:
            try:
                chunk = fh.readline(LINE_CAP + 1)
            except OSError:
                return
            if not chunk:
                return
            line_no += 1
            if len(chunk) <= LINE_CAP and chunk.endswith(b"\n"):
                yield line_no, chunk
                continue
            if len(chunk) <= LINE_CAP and not chunk.endswith(b"\n"):
                yield line_no, chunk
                return
            while chunk and not chunk.endswith(b"\n"):
                try:
                    chunk = fh.readline(LINE_CAP + 1)
                except OSError:
                    chunk = b""
            yield line_no, None


def _json_record(raw: bytes | None, stats: Stats) -> dict | None:
    stats.records_seen += 1
    if raw is None:
        stats.oversized_records += 1
        return None
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        stats.malformed_records += 1
        return None
    return record if isinstance(record, dict) else None


def _source_label(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("type", "kind", "source"):
            if isinstance(value.get(key), str):
                return value[key]
        return json.dumps(value, sort_keys=True, separators=(",", ":"))[:200]
    return ""


def _metadata_from_payload(meta: FileMeta, payload: dict, timestamp: str) -> None:
    if isinstance(payload.get("id"), str):
        meta.session_id = payload["id"]
    if isinstance(payload.get("cwd"), str):
        meta.cwd = payload["cwd"]
    meta.thread_source = _source_label(payload.get("thread_source"))
    meta.originator = _source_label(payload.get("originator"))
    git = payload.get("git")
    if isinstance(git, dict) and isinstance(git.get("branch"), str):
        meta.git_branch = git["branch"]
    if timestamp:
        meta.started_at = timestamp


def read_file_meta(path: Path) -> FileMeta:
    mtime = safe_mtime(path)
    meta = FileMeta(path=path, session_id=_fallback_session_id(path), mtime=mtime)
    stats = Stats()
    found = False
    for line_no, raw in iter_bounded_lines(path):
        if line_no > 64:
            break
        if raw is None or b'"session_meta"' not in raw:
            if found:
                break
            continue
        record = _json_record(raw, stats)
        if not record or record.get("type") != "session_meta":
            continue
        payload = record.get("payload")
        if isinstance(payload, dict) and not found:
            _metadata_from_payload(meta, payload, str(record.get("timestamp") or ""))
            found = True
    return meta


def _is_injected(text: str) -> bool:
    value = text.lstrip().lower()
    return any(value.startswith(prefix) for prefix in _INJECTED_PREFIXES)


def _is_human_source(source: str) -> bool:
    lowered = source.lower()
    return not any(marker in lowered for marker in _NON_HUMAN_SOURCES)


def redact(text: str) -> tuple[str, int]:
    count = 0
    for pattern, label in _SECRET_PATTERNS:
        text, replacements = pattern.subn(f"[REDACTED:{label}]", text)
        count += replacements
    return text, count


def _annotation_text(text: str) -> str:
    if not text.lstrip().lower().startswith("# response annotations:"):
        return text
    match = re.search(r"<response-annotations>\s*(.*?)\s*</response-annotations>", text, re.S | re.I)
    parts: list[str] = []
    if match:
        try:
            annotations = json.loads(match.group(1))
        except (ValueError, RecursionError):
            annotations = []
        if isinstance(annotations, list):
            for annotation in annotations:
                if isinstance(annotation, dict) and isinstance(annotation.get("annotation"), str):
                    parts.append(annotation["annotation"].strip())
    request = re.split(r"^## My request:\s*$", text, maxsplit=1, flags=re.M | re.I)
    if len(request) == 2 and request[1].strip():
        parts.append(request[1].strip())
    return "\n\n".join(part for part in parts if part)


def _message_text(payload: dict, role: str) -> tuple[str, int]:
    content = payload.get("content")
    if isinstance(content, str):
        content = _annotation_text(content) if role == "user" else content
        return ("", 1) if _is_injected(content) else (content, 0)
    if not isinstance(content, list):
        message = payload.get("message")
        if not isinstance(message, str):
            return "", 0
        message = _annotation_text(message) if role == "user" else message
        return (("", 1) if _is_injected(message) else (message, 0))
    wanted = "input_text" if role == "user" else "output_text"
    parts = []
    skipped = 0
    for part in content:
        if not isinstance(part, dict) or part.get("type") != wanted:
            continue
        text = part.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        text = _annotation_text(text) if role == "user" else text
        if not text.strip() or _is_injected(text):
            skipped += 1
            continue
        parts.append(text)
    return "\n\n".join(parts), skipped


def extract_turns(path: Path, *, include_non_human: bool = False) -> tuple[list[Turn], Stats]:
    stats = Stats(files_scanned=1)
    meta = FileMeta(path=path, session_id=_fallback_session_id(path), mtime=safe_mtime(path))
    own_meta_seen = False
    turns: list[Turn] = []
    for line_no, raw in iter_bounded_lines(path):
        if raw is None:
            stats.records_seen += 1
            stats.oversized_records += 1
            continue
        if b'"session_meta"' in raw:
            record = _json_record(raw, stats)
            if (
                not own_meta_seen
                and record
                and record.get("type") == "session_meta"
                and isinstance(record.get("payload"), dict)
            ):
                _metadata_from_payload(meta, record["payload"], str(record.get("timestamp") or ""))
                own_meta_seen = True
            continue
        if b'"response_item"' not in raw or b'"message"' not in raw:
            continue
        record = _json_record(raw, stats)
        if not record or record.get("type") != "response_item":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "message":
            continue
        role = payload.get("role")
        if role not in ("user", "assistant"):
            continue
        if not include_non_human and not _is_human_source(meta.thread_source):
            continue
        text, injected_skipped = _message_text(payload, role)
        stats.injected_parts_skipped += injected_skipped
        if not text.strip():
            continue
        text, redactions = redact(text.strip())
        stats.redactions += redactions
        truncated = len(text) > TEXT_CAP
        if truncated:
            text = text[:TEXT_CAP] + "\n[… turn truncated by session-history …]"
        item_id = payload.get("id")
        if not isinstance(item_id, str) or not item_id:
            item_id = f"{path.name}:L{line_no}"
        ordinal = record.get("ordinal")
        if not isinstance(ordinal, int):
            ordinal = line_no
        turns.append(
            Turn(
                session_id=meta.session_id,
                path=path,
                line=line_no,
                ordinal=ordinal,
                item_id=item_id,
                timestamp=str(record.get("timestamp") or ""),
                role=role,
                text=text,
                cwd=meta.cwd,
                thread_source=meta.thread_source,
                git_branch=meta.git_branch,
                mtime=meta.mtime,
            )
        )
        stats.messages_kept += 1
    return turns, stats


def all_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    files = [path for path in root.rglob("*.jsonl") if path.is_file()]
    return sorted(files, key=safe_mtime, reverse=True)


def file_inventory(root: Path) -> list[FileMeta]:
    return [read_file_meta(path) for path in all_files(root)]


def files_for_scope(
    inventory: list[FileMeta], scope: str, *, cwd: str, session_id: str
) -> list[FileMeta]:
    human = [meta for meta in inventory if _is_human_source(meta.thread_source)]
    if scope == "current-task":
        if not session_id:
            return []
        return [meta for meta in human if meta.session_id == session_id or session_id in meta.path.name]
    if scope == "current-project":
        resolved = str(Path(cwd).expanduser().resolve())
        return [meta for meta in human if meta.cwd and str(Path(meta.cwd).expanduser().resolve()) == resolved]
    return human


def _cjk_tokens(run: str) -> list[str]:
    chars = list(run)
    tokens = chars[:]
    tokens.extend(chars[index] + chars[index + 1] for index in range(len(chars) - 1))
    if 1 < len(run) <= 8:
        tokens.append(run)
    return tokens


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word in _WORD_RE.findall(text):
        if _CJK_RE.fullmatch(word):
            tokens.extend(_cjk_tokens(word))
            continue
        lowered = word.lower()
        tokens.append(lowered)
        for camel in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", word):
            value = camel.lower()
            if value != lowered:
                tokens.append(value)
        for part in re.split(r"[_./\-]+", lowered):
            if part and part != lowered:
                tokens.append(part)
    return [token for token in tokens if token not in _STOPWORDS and (len(token) >= 2 or _CJK_RE.fullmatch(token))]


def normalize_query(query: str) -> tuple[str, list[str]]:
    lowered = " " + query.lower().strip() + " "
    for phrase in sorted(_TRIGGER_PHRASES, key=len, reverse=True):
        lowered = lowered.replace(" " + phrase + " ", " ")
    cleaned = re.sub(r"\s+", " ", lowered).strip()
    return cleaned, list(dict.fromkeys(tokenize(cleaned)))


def _collapse(text: str, cap: int = GIST_CAP) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    return value if len(value) <= cap else value[:cap] + " …"


def _turn_order(turn: Turn) -> tuple:
    try:
        epoch = datetime.fromisoformat(turn.timestamp.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        epoch = turn.mtime
    return (epoch, turn.ordinal, str(turn.path), turn.line)


def load_turns(metas: list[FileMeta]) -> tuple[list[Turn], Stats]:
    combined: list[Turn] = []
    total = Stats()
    seen: set[tuple[str, str]] = set()
    for meta in metas:
        turns, stats = extract_turns(meta.path)
        total.add(stats)
        for turn in turns:
            key = (turn.session_id, turn.item_id)
            if key in seen:
                continue
            seen.add(key)
            combined.append(turn)
    combined.sort(key=_turn_order)
    return combined, total


def exclude_invoking_turn(turns: list[Turn], session_id: str, query: str) -> tuple[list[Turn], str, str]:
    current_users = [turn for turn in turns if turn.session_id == session_id and turn.role == "user"] if session_id else []
    resolution = "session-id" if current_users else ""
    if not current_users and not session_id:
        normalized_query = _collapse(query, TEXT_CAP).lower()
        possible = [
            turn
            for turn in turns
            if turn.role == "user" and normalized_query and normalized_query in _collapse(turn.text, TEXT_CAP).lower()
        ]
        if possible:
            newest = max(possible, key=_turn_order)
            newest_file_time = max((turn.mtime for turn in turns), default=0.0)
            if newest_file_time - newest.mtime <= 300:
                current_users = [newest]
                resolution = "recent-query-match"
    if not current_users:
        return turns, "", "unavailable"
    latest = max(current_users, key=_turn_order)
    return [turn for turn in turns if turn is not latest], latest.item_id, resolution


def _distinct_key(turn: Turn) -> tuple[str, str]:
    return turn.session_id, re.sub(r"\s+", " ", turn.text).strip().lower()


def rank_turns(turns: list[Turn], query: str, limit: int) -> tuple[str, list[Turn], list[str]]:
    cleaned, terms = normalize_query(query)
    qset = set(terms)
    if not qset:
        return "empty_query", [], terms
    if not turns:
        return "no_match", [], terms
    for turn in turns:
        turn.tokens = tokenize(turn.text)
    searchable = [turn for turn in turns if turn.tokens]
    if not searchable:
        return "no_match", [], terms
    document_frequency: Counter[str] = Counter()
    for turn in searchable:
        document_frequency.update(set(turn.tokens) & qset)
    idf = {
        term: math.log(1 + (len(searchable) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
        for term in qset
        if document_frequency[term]
    }
    if not idf:
        return "no_match", [], terms
    average_length = sum(len(turn.tokens) for turn in searchable) / len(searchable)
    oldest = min((turn.mtime for turn in searchable), default=0.0)
    newest = max((turn.mtime for turn in searchable), default=oldest)
    scored: list[Turn] = []
    for turn in searchable:
        frequencies = Counter(turn.tokens)
        matched = sum(1 for term in qset if frequencies[term])
        base = 0.0
        for term, term_idf in idf.items():
            frequency = frequencies[term]
            if not frequency:
                continue
            denominator = frequency + BM25_K1 * (
                1 - BM25_B + BM25_B * len(turn.tokens) / average_length
            )
            base += term_idf * (frequency * (BM25_K1 + 1)) / denominator
        if base <= 0:
            continue
        boost = USER_BOOST if turn.role == "user" else 1.0
        if _CUE.search(turn.text):
            boost *= CUE_BOOST
        if cleaned and len(qset) > 1 and cleaned in turn.text.lower():
            boost *= PHRASE_BOOST
        if newest > oldest:
            boost *= 1.0 + RECENCY_BOOST * ((turn.mtime - oldest) / (newest - oldest))
        turn.score = base * boost
        turn.matched = matched
        turn.coverage = matched / len(qset)
        scored.append(turn)
    scored.sort(key=lambda turn: turn.score, reverse=True)
    distinct: list[Turn] = []
    seen: set[tuple[str, str]] = set()
    for turn in scored:
        key = _distinct_key(turn)
        if key in seen:
            continue
        if len(qset) > 1 and (turn.matched < 2 or turn.coverage < CANDIDATE_COVERAGE):
            continue
        seen.add(key)
        distinct.append(turn)
        if len(distinct) >= limit:
            break
    if not distinct:
        return "no_match", [], terms
    top = distinct[0]
    second = next(
        (turn.score for turn in scored if _distinct_key(turn) != _distinct_key(top)),
        0.0,
    )
    margin_ok = second <= 0 or top.score >= CONFIDENT_MARGIN * second
    status = "ambiguous"
    if len(qset) > 1 and top.coverage >= CONFIDENT_COVERAGE and margin_ok and top.role == "user":
        status = "confident"
    return status, distinct, terms


def _relative_transcript(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def turn_json(turn: Turn, root: Path, rank: int) -> dict:
    return {
        "rank": rank,
        "score": round(turn.score, 3),
        "coverage": round(turn.coverage, 3),
        "matched_terms": turn.matched,
        "role": turn.role,
        "timestamp": turn.timestamp,
        "excerpt": _collapse(turn.text),
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


def search_history(
    root: Path,
    query: str,
    *,
    cwd: str,
    scope: str,
    explicit_session_id: str = "",
    roles: str = "both",
    limit: int = DEFAULT_LIMIT,
) -> dict:
    started = time.monotonic()
    inventory = file_inventory(root)
    session_id = current_session_id(explicit_session_id)
    scopes = [scope] if scope != "auto" else ["current-task", "current-project", "all"]
    attempts = []
    results: list[tuple[str, list[Turn], list[str], Stats, str, str, str]] = []
    for chosen_scope in scopes:
        metas = files_for_scope(inventory, chosen_scope, cwd=cwd, session_id=session_id)
        if not metas:
            attempts.append({"scope": chosen_scope, "files": 0, "status": "unavailable"})
            continue
        turns, stats = load_turns(metas)
        turns, excluded_item, exclusion_resolution = exclude_invoking_turn(turns, session_id, query)
        if roles != "both":
            turns = [turn for turn in turns if turn.role == roles]
        status, hits, terms = rank_turns(turns, query, limit)
        attempts.append({"scope": chosen_scope, "files": len(metas), "turns": len(turns), "status": status})
        results.append((status, hits, terms, stats, chosen_scope, excluded_item, exclusion_resolution))
        if status == "confident" or status == "empty_query":
            break
    if not results:
        return {
            "status": "no_match",
            "reason": "no matching transcript scope is available",
            "query": redact(query)[0],
            "scope_attempts": attempts,
            "current_session_id": session_id or None,
            "candidates": [],
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }
    confident = next((result for result in results if result[0] == "confident"), None)
    ambiguous = [result for result in results if result[0] == "ambiguous" and result[1]]
    if confident:
        final = confident
    elif ambiguous:
        final = max(ambiguous, key=lambda result: (result[1][0].coverage, result[1][0].score))
    else:
        final = results[-1]
    status, hits, terms, stats, used_scope, excluded_item, exclusion_resolution = final
    output = {
        "status": status,
        "query": redact(query)[0],
        "scope_used": used_scope,
        "scope_attempts": attempts,
        "current_session_id": session_id or None,
        "excluded_latest_user_item": excluded_item or None,
        "invoking_turn_resolution": exclusion_resolution,
        "stats": stats.as_dict(),
        "candidates": [turn_json(turn, root, index + 1) for index, turn in enumerate(hits)],
        "elapsed_ms": round((time.monotonic() - started) * 1000),
    }
    if status == "empty_query":
        output["reason"] = "the query contained no searchable terms; retry with concrete names, values, or identifiers"
    return output


def show_context(
    root: Path,
    session_id: str,
    item_id: str,
    *,
    before: int,
    after: int,
    max_chars: int,
) -> dict:
    max_chars = min(max(max_chars, 1000), 50000)
    inventory = file_inventory(root)
    exact = [meta for meta in inventory if meta.session_id == session_id]
    matches = exact or [meta for meta in inventory if meta.session_id.startswith(session_id)]
    session_ids = sorted({meta.session_id for meta in matches})
    if not matches:
        return {"status": "not_found", "reason": f"no session matches {session_id!r}"}
    if len(session_ids) > 1:
        return {"status": "ambiguous_session", "candidates": session_ids[:10]}
    turns, stats = load_turns(matches)
    anchor_matches = [index for index, turn in enumerate(turns) if turn.item_id == item_id]
    if not anchor_matches:
        anchor_matches = [index for index, turn in enumerate(turns) if turn.item_id.startswith(item_id)]
    if not anchor_matches:
        return {"status": "not_found", "reason": f"no item matches {item_id!r}", "stats": stats.as_dict()}
    if len(anchor_matches) > 1:
        return {
            "status": "ambiguous_item",
            "candidates": [turns[index].item_id for index in anchor_matches[:10]],
            "stats": stats.as_dict(),
        }
    anchor = anchor_matches[0]
    lo, hi = max(0, anchor - before), min(len(turns), anchor + after + 1)
    window_indexes = list(range(lo, hi))
    chosen: dict[int, tuple[str, bool]] = {}
    anchor_text = turns[anchor].text[:max_chars]
    chosen[anchor] = (anchor_text, len(anchor_text) < len(turns[anchor].text))
    remaining = max_chars - len(anchor_text)
    for distance in range(1, max(before, after) + 1):
        for index in (anchor - distance, anchor + distance):
            if index not in window_indexes or index in chosen or remaining <= 0:
                continue
            text = turns[index].text[:remaining]
            chosen[index] = (text, len(text) < len(turns[index].text))
            remaining -= len(text)
    output = []
    for index in sorted(chosen):
        turn = turns[index]
        text, _ = chosen[index]
        output.append(
            {
                "role": turn.role,
                "timestamp": turn.timestamp,
                "text": text,
                "is_anchor": index == anchor,
                "locator": {
                    "session_id": turn.session_id,
                    "item_id": turn.item_id,
                    "transcript": _relative_transcript(turn.path, root),
                    "line": turn.line,
                    "ordinal": turn.ordinal,
                },
            }
        )
    truncated = len(chosen) < len(window_indexes) or any(value[1] for value in chosen.values())
    return {
        "status": "ok",
        "session_id": session_ids[0],
        "anchor_item_id": turns[anchor].item_id,
        "turns": output,
        "truncated": truncated,
        "stats": stats.as_dict(),
    }


def list_sessions(root: Path, *, cwd: str, scope: str, limit: int) -> dict:
    inventory = file_inventory(root)
    session_id = current_session_id()
    chosen = files_for_scope(inventory, scope, cwd=cwd, session_id=session_id)
    grouped: dict[str, list[FileMeta]] = {}
    for meta in chosen:
        grouped.setdefault(meta.session_id, []).append(meta)
    sessions = []
    for sid, metas in grouped.items():
        newest = max(metas, key=lambda meta: meta.mtime)
        oldest = min(metas, key=lambda meta: meta.mtime)
        sessions.append(
            {
                "session_id": sid,
                "cwd": newest.cwd,
                "thread_source": newest.thread_source,
                "originator": newest.originator,
                "git_branch": newest.git_branch,
                "files": len(metas),
                "started_at": oldest.started_at,
                "last_activity": datetime.fromtimestamp(newest.mtime).astimezone().isoformat(),
                "transcripts": [_relative_transcript(meta.path, root) for meta in sorted(metas, key=lambda meta: meta.mtime)],
            }
        )
    sessions.sort(key=lambda value: value["last_activity"], reverse=True)
    return {"status": "ok", "scope": scope, "sessions": sessions[:limit], "total": len(sessions)}


def doctor(root: Path, cwd: str) -> dict:
    inventory = file_inventory(root)
    sid = current_session_id()
    current = files_for_scope(inventory, "current-task", cwd=cwd, session_id=sid)
    project = files_for_scope(inventory, "current-project", cwd=cwd, session_id=sid)
    return {
        "status": "ok" if root.is_dir() else "missing_store",
        "root": str(root),
        "transcript_files": len(inventory),
        "current_session_id": sid or None,
        "current_task_files": len(current),
        "current_project_files": len(project),
        "cwd": str(Path(cwd).expanduser().resolve()),
        "read_only": True,
        "persistent_index": False,
    }


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
    show.add_argument("--before", type=int, choices=range(0, 21), default=3)
    show.add_argument("--after", type=int, choices=range(0, 21), default=5)
    show.add_argument("--max-chars", type=int, default=12000)

    sessions = commands.add_parser("sessions", help="list candidate Codex sessions")
    sessions.add_argument("--cwd", default=os.getcwd())
    sessions.add_argument("--scope", choices=("current-task", "current-project", "all"), default="current-project")
    sessions.add_argument("--limit", type=int, choices=range(1, 101), default=20)

    diagnose = commands.add_parser("doctor", help="inspect transcript discovery and current-task resolution")
    diagnose.add_argument("--cwd", default=os.getcwd())
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = (args.root or session_root()).expanduser().resolve()
    try:
        if args.command == "search":
            output = search_history(
                root,
                args.query,
                cwd=args.cwd,
                scope=args.scope,
                explicit_session_id=args.session_id,
                roles=args.roles,
                limit=args.limit,
            )
        elif args.command == "show":
            output = show_context(
                root,
                args.session_id,
                args.item_id,
                before=args.before,
                after=args.after,
                max_chars=args.max_chars,
            )
        elif args.command == "sessions":
            output = list_sessions(root, cwd=args.cwd, scope=args.scope, limit=args.limit)
        else:
            output = doctor(root, args.cwd)
    except Exception as exc:  # Keep a retrieval failure structured for the calling agent.
        output = {"status": "error", "error": f"{type(exc).__name__}: {exc}", "root": str(root)}
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
