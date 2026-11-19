"""recall backend for Antigravity CLI (agy) conversations.

The shared engine (`shared/`) loads this module as `backend("agy")`. It owns the agy store's
layout and speaker rules; redaction, tokenizing and dates come from the Claude backend, which
the engine uses as the one language module for every store. See references/transcript-store.md.

One conversation is one append-only JSONL file of steps:
  <store>/brain/<conversation-uuid>/.system_generated/logs/transcript_full.jsonl
Titles, workspaces and subagent parents live in <store>/conversation_summaries.db (read-only).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

PARSER_VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

TRANSCRIPT = ".system_generated/logs/transcript_full.jsonl"
_REQUEST = re.compile(r"<USER_REQUEST>\n?(.*?)\n?</USER_REQUEST>", re.S)
_SYSTEM = re.compile(r"\n<SYSTEM_MESSAGE>\n?(.*)\n?</SYSTEM_MESSAGE>\s*\Z", re.S)
# A message the agentapi pushed into the conversation: another session (agent-msg), the parent of a
# subagent, the harness itself (sender=system) or one of this conversation's own tasks.
_PUSHED = re.compile(r"\[Message\] timestamp=\S* sender=(\S*) priority=\S* content=(.*)\Z", re.S)
_STAMPS = re.compile(r"\A(?:(?:Created|Completed) At: [^\n]*\n)+")
# Prompts other tools type into a session (agent-team briefs, codex-exec lines, tmux-persist restarts):
# agy records them as user input, the user did not write them. Same rule as the Claude backend's _AUTOMATED.
_AUTOMATED = re.compile(r"^(#+\s|你是独立|你是新的|这个会话刚被重启|\[cx )")


# ---------------------------------------------------------------------------- store
def store_root() -> Path:
    override = os.environ.get("AGY_RECALL_ROOT")
    return Path(override).expanduser() if override else Path.home() / ".gemini" / "antigravity-cli"


def transcript_paths(prefix: str = "") -> list[Path]:
    """Transcripts of the conversations whose id starts with `prefix` (all of them for '')."""
    root = store_root() / "brain"
    return sorted(root.glob(f"{prefix}*/{TRANSCRIPT}")) if root.is_dir() else []


def session_of(path: Path) -> str:
    return path.parents[2].name


def current_session_id() -> str:
    return os.environ.get("ANTIGRAVITY_CONVERSATION_ID", "")


def conversations() -> dict[str, dict]:
    """{conversation id: {title, project, parent}} from agy's summaries database; the workspace
    falls back to cache/last_conversations.json (workspace -> latest conversation)."""
    return _conversations(str(store_root()))


@lru_cache(maxsize=4)
def _conversations(root: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    database = Path(root) / "conversation_summaries.db"
    if database.is_file():
        try:
            with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True, timeout=10)) as db:
                rows = db.execute("SELECT conversation_id, title, workspace_uris, parent_conversation_id"
                                  " FROM conversation_summaries").fetchall()
        except sqlite3.Error as exc:   # agy changed or locked it: say so, the transcripts still read
            print(f"recall: agy titles, workspaces and subagent parents unavailable ({database}: {exc})",
                  file=sys.stderr)
            rows = []
        for conversation, title, uris, parent in rows:
            try:
                workspaces = json.loads(uris or "[]")
            except ValueError:
                workspaces = []
            first = workspaces[0] if workspaces and isinstance(workspaces[0], str) else ""
            found[conversation] = {"title": (title or "").strip(), "parent": parent or "",
                                   "project": unquote(urlparse(first).path) if first.startswith("file:") else first}
    try:
        latest = json.loads((Path(root) / "cache" / "last_conversations.json").read_text())
    except (OSError, ValueError):
        latest = {}
    for workspace, conversation in sorted(latest.items(), key=lambda pair: len(pair[0])) if isinstance(latest, dict) else ():
        entry = found.setdefault(conversation, {"title": "", "parent": "", "project": ""})
        entry["project"] = entry["project"] or workspace          # the shortest path: the workspace root
    return found


# ---------------------------------------------------------------------------- steps
def request_text(content: str) -> str:
    """The typed request of a USER_INPUT step, without agy's metadata and settings blocks."""
    found = _REQUEST.search(content)
    return (found.group(1) if found else content).strip()


def system_text(content: str) -> str:
    """The body of a SYSTEM_MESSAGE step, without agy's 'not actually sent by the user' preamble."""
    found = _SYSTEM.search(content)
    return (found.group(1) if found else content).strip()


def output_text(content: str) -> str:
    """A tool output without agy's leading Created At / Completed At stamps."""
    return _STAMPS.sub("", content).strip()


def tool_text(name: str, args) -> str:
    """A tool call's arguments as the text a person would read (run_command: the command line)."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return args
    if not isinstance(args, dict):
        return json.dumps(args, ensure_ascii=False)
    if name == "run_command" and isinstance(args.get("CommandLine"), str):
        return args["CommandLine"]
    if name == "read_file" and isinstance(args.get("Path"), str):
        return args["Path"]
    if name == "write_file":
        return f"{args.get('Path', '')}\n{args.get('Content', '')}"
    if name == "edit_file":
        return f"{args.get('Path', '')}\n--- old\n{args.get('Target', '')}\n+++ new\n{args.get('Replacement', '')}"
    return json.dumps(args, ensure_ascii=False)


def message(step: dict) -> tuple[str, str, str] | None:
    """(role, text, sender) when a step is conversation, else None. The person's typed request is
    `user` (`automated` when a tool typed it); a message pushed by another session, a subagent's parent or the harness's agent-msg
    relay is `peer` (sender kept); this conversation's own task results and scheduled prompts, and
    harness notices, are `automated`. Hook injections and other system text are events, not speech."""
    kind = step.get("type")
    content = step.get("content") if isinstance(step.get("content"), str) else ""
    if kind == "USER_INPUT":
        text = request_text(content)
        return ("automated" if _AUTOMATED.match(text) else "user", text, "") if text else None
    if kind == "PLANNER_RESPONSE":
        return ("assistant", content.strip(), "") if content.strip() else None
    if kind == "SYSTEM_MESSAGE":
        pushed = _PUSHED.match(system_text(content))
        if not pushed:
            return None
        sender, text = pushed.group(1), pushed.group(2).strip()
        automated = "/task-" in sender or (sender == "system" and text.startswith("[Notice]"))
        return ("automated" if automated else "peer", text, sender) if text else None
    return None


# ---------------------------------------------------------------------------- index feed
def new_cursor() -> dict:
    """Resume point for an append-only transcript: bytes and physical lines already consumed."""
    return {"offset": 0, "line": 0}


def file_rows(path: Path, cursor: dict) -> list[tuple[int, str, str, str]]:
    """(line, role, text, timestamp) of the messages appended since `cursor`, unredacted. A last
    line without its newline is left for the next pass (agy is still writing it)."""
    rows = []
    with Path(path).open("rb") as handle:
        handle.seek(cursor["offset"])
        while (raw := handle.readline()).endswith(b"\n"):
            cursor["offset"] += len(raw)
            cursor["line"] += 1
            try:
                step = json.loads(raw)
            except ValueError:
                continue
            said = message(step) if isinstance(step, dict) else None
            if said:
                rows.append((cursor["line"], said[0], said[1], str(step.get("created_at") or "")))
    return rows


def confirmation_line(date: str, session: str, role: str, gist: str) -> str:
    """The provenance line shared with the Claude and Codex builds."""
    who = "" if role == "user" else "agent turn, unconfirmed by user: "
    return f"recall: {date} · {session[:8]} · {who}{gist}"
