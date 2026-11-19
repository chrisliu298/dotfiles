"""Raw transcript reading for the recall CLI: one record -> messages, commands and outputs.

The index (index.py) ranks conversation messages only. Everything that must be exact or
complete — a command, a tool output, a subagent transcript, a spilled tool result — is read
here straight from the transcript, so an item's text is the recorded text (redacted), not an
index snippet. Speaker rules come from the source backends (`speaker`, `_message_text`), so
the index and this reader agree on who said what.

An item is addressed by a ref, `cl:`, `cx:` or `ag:<session>:<line>[.<block>]`: a Claude record or
an agy step can hold several blocks (text, tool calls, tool results), a Codex record one.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

PREFIX = {"claude": "cl", "codex": "cx", "agy": "ag"}
SOURCE = {v: k for k, v in PREFIX.items()}
MARKER = "⟦recall⟧"          # heads every CLI output, so a later grep skips its own echoes
_RECALL_CALL = re.compile(r"(^|[\s;&|(])recall\s+(search|grep|session|open|timeline|sessions)\b")
_SPILL = re.compile(r"<persisted-output>.*?saved to:\s*(\S+)", re.S)


@dataclass
class Item:
    line: int
    block: int
    kind: str                 # message | command | output | event
    role: str                 # user | assistant | peer | automated | tool | system
    text: str
    time: str = ""
    tool: str = ""
    call: str = ""
    error: bool = False
    spill: str = ""           # file holding the full output when the transcript kept a preview
    extra: dict = field(default_factory=dict)

    def ref(self, source: str, session: str) -> str:
        return f"{PREFIX[source]}:{session}:{self.line}" + (f".{self.block}" if self.block else "")

    def json(self, source: str, session: str, text: str | None = None) -> dict:
        out = {"ref": self.ref(source, session), "time": self.time, "kind": self.kind, "role": self.role}
        if self.tool:
            out["tool"] = self.tool
        if self.error:
            out["error"] = True
        if self.spill:
            out["spill"] = self.spill
        out["text"] = self.text if text is None else text
        out["chars"] = len(self.text)
        return out


_RG_META = set("\\.+*?()|[]{}^$")


def prefilter(pattern: str) -> str:
    """A ripgrep regex that finds `pattern` in raw JSONL lines however JSON escaped it.

    Transcripts store text JSON-encoded, sometimes twice (a tool's JSON arguments inside the
    record), so quotes, backslashes and newlines appear escaped and non-ASCII may appear as
    \\uXXXX. Only the longest run free of such characters is matched; the exact match then
    runs on the decoded item text."""
    runs = re.findall(r"[ -!#-\[\]-~]+|[^\x00-\x7f]+", pattern)       # printable ASCII minus " and \\
    run = max(runs, key=len, default="")
    if not run:
        return "."
    if run.isascii():
        return "".join("\\" + c if c in _RG_META else c for c in run)
    escaped = "".join(f"\\\\+u{ord(c):04x}" if ord(c) < 0x10000 else "" for c in run)
    return f"(?:{run}|(?i:{escaped}))" if escaped else run


def is_recall_echo(item: Item) -> bool:
    """A recall invocation or its printed result — evidence of a lookup, not of the past."""
    return MARKER in item.text or (item.kind == "command" and bool(_RECALL_CALL.search(item.text[:400])))


# ---------------------------------------------------------------------------- Claude
def _tool_input(name: str, data) -> str:
    if not isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False)
    if name == "Bash" and isinstance(data.get("command"), str):
        return data["command"]
    if name == "Write":
        return f"{data.get('file_path', '')}\n{data.get('content', '')}"
    if name == "Edit":
        return f"{data.get('file_path', '')}\n--- old\n{data.get('old_string', '')}\n+++ new\n{data.get('new_string', '')}"
    if name == "Read":
        return str(data.get("file_path", ""))
    return json.dumps(data, ensure_ascii=False)


def _result_text(content) -> str:
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return content if isinstance(content, str) else ""


def claude_items(api, rec: dict, line: int, questions: set | None = None) -> list[Item]:
    """Items of one Claude record. Messages pass the backend's speaker and injection rules.
    `questions` collects AskUserQuestion call ids across a read, so their answers stay user words
    (a lone record still shows its answer through `toolUseResult.answers`)."""
    t, ts = rec.get("type"), str(rec.get("timestamp") or "")
    questions = set() if questions is None else questions
    if t == "attachment":
        att = rec.get("attachment") or {}
        if att.get("type") != "queued_command":
            return []
        prompt = att.get("prompt")
        if isinstance(prompt, list):
            prompt = " ".join(b.get("text", "") for b in prompt if isinstance(b, dict))
        role, text = api.speaker(att, prompt if isinstance(prompt, str) else "")
        return [Item(line, 0, "message", role, api.redact(text), ts)] if role and not api.is_injected(text) else []
    if t == "system":
        detail = rec.get("content") if isinstance(rec.get("content"), str) else ""
        label = str(rec.get("subtype") or "system")
        return [Item(line, 0, "event", "system", api.redact(f"{label}: {detail}".strip(": ")), ts, tool=label)]
    if t not in ("user", "assistant"):
        return []
    if rec.get("isCompactSummary"):
        return [Item(line, 0, "event", "system", "compacted: the conversation was summarized here", ts, tool="compacted")]
    content = (rec.get("message") or {}).get("content")
    blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
    if not isinstance(blocks, list):
        return []
    items: list[Item] = []
    texts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    if any(x.strip() for x in texts):
        joined = " ".join(texts)
        role, text = ("assistant", joined.strip()) if t == "assistant" else api.speaker(rec, joined)
        if role and not api.is_injected(text):
            items.append(Item(line, 0, "message", role, api.redact(text), ts))
    answered = isinstance(rec.get("toolUseResult"), dict) and "answers" in rec["toolUseResult"]
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "tool_use":
            name = str(b.get("name") or "")
            if name == "AskUserQuestion" and b.get("id"):
                questions.add(b["id"])
            items.append(Item(line, len(items), "command", "assistant", api.redact(_tool_input(name, b.get("input"))),
                              ts, tool=name, call=str(b.get("id") or "")))
        elif b.get("type") == "tool_result":
            text = _result_text(b.get("content"))
            if not b.get("is_error") and (answered or b.get("tool_use_id") in questions):
                items.append(Item(line, len(items), "message", "user", api.redact(text), ts, call=str(b.get("tool_use_id"))))
                continue
            spill = _SPILL.search(text[:2000])
            items.append(Item(line, len(items), "output", "tool", api.redact(text), ts, call=str(b.get("tool_use_id") or ""),
                              error=bool(b.get("is_error")), spill=spill.group(1) if spill else ""))
    return items


# ---------------------------------------------------------------------------- Codex
def _codex_output(value) -> str:
    if isinstance(value, list):
        return "\n".join(b.get("text", "") for b in value if isinstance(b, dict))
    if isinstance(value, str):
        try:
            data = json.loads(value)
        except ValueError:
            return value
        if isinstance(data, dict) and isinstance(data.get("output"), str):
            return data["output"]
        return value
    return json.dumps(value, ensure_ascii=False) if value is not None else ""


def _codex_arguments(value) -> str:
    if isinstance(value, str):
        try:
            data = json.loads(value)
        except ValueError:
            return value
    else:
        data = value
    if isinstance(data, dict):
        for key in ("cmd", "command"):
            if isinstance(data.get(key), str):
                return data[key]
            if isinstance(data.get(key), list):
                return " ".join(map(str, data[key]))
    return json.dumps(data, ensure_ascii=False)


_CODEX_EVENTS = {"task_started": (), "task_complete": ("last_agent_message",), "turn_aborted": ("reason",),
                 "error": ("message",), "stream_error": ("message",)}


def codex_items(api, language, rec: dict, line: int) -> list[Item]:
    p, ts = rec.get("payload"), str(rec.get("timestamp") or "")
    if rec.get("type") == "compacted":
        return [Item(line, 0, "event", "system", "compacted: the conversation was summarized here", ts, tool="compacted")]
    if rec.get("type") == "event_msg" and isinstance(p, dict) and p.get("type") in _CODEX_EVENTS:
        label = p["type"]
        detail = " ".join(str(p[k]) for k in _CODEX_EVENTS[label] if p.get(k))
        return [Item(line, 0, "event", "system", language.redact(f"{label}: {detail}".strip(": ")), ts, tool=label)]
    if rec.get("type") != "response_item" or not isinstance(p, dict):
        return []
    kind = p.get("type")
    if kind == "message" and p.get("role") in ("user", "assistant"):
        text, _ = api._message_text(p, p["role"])
        return [Item(line, 0, "message", p["role"], language.redact(text.strip()), ts)] if text.strip() else []
    if kind == "agent_message":
        text, _ = api._message_text(p, "user")
        who = f"{p.get('author', '')} → {p.get('recipient', '')}"
        return [Item(line, 0, "message", "peer", language.redact(text.strip()), ts, tool=who)] if text.strip() else []
    if kind in ("function_call", "custom_tool_call", "local_shell_call"):
        raw = p.get("arguments") if kind == "function_call" else p.get("input") if kind == "custom_tool_call" else p.get("action")
        return [Item(line, 0, "command", "assistant", language.redact(_codex_arguments(raw)), ts,
                     tool=str(p.get("name") or kind), call=str(p.get("call_id") or ""))]
    if kind in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
        return [Item(line, 0, "output", "tool", language.redact(_codex_output(p.get("output"))), ts,
                     call=str(p.get("call_id") or ""))]
    return []


# ---------------------------------------------------------------------------- agy
def agy_items(api, language, step: dict, line: int) -> list[Item]:
    """Items of one agy step: its message (speaker rules from the backend), then each tool call of a
    planner response, or the tool output, compaction, error or system text the step records."""
    kind, ts = step.get("type"), str(step.get("created_at") or "")
    content = step.get("content") if isinstance(step.get("content"), str) else ""
    items: list[Item] = []
    said = api.message(step)
    if said:
        role, text, sender = said
        items.append(Item(line, 0, "message", role, language.redact(text), ts, tool=sender))
    if kind == "PLANNER_RESPONSE":
        for call in step.get("tool_calls") or []:
            if isinstance(call, dict):
                name = str(call.get("name") or "")
                items.append(Item(line, len(items), "command", "assistant",
                                  language.redact(api.tool_text(name, call.get("args"))), ts, tool=name))
    elif kind == "GENERIC":            # status RUNNING: a background task's start notice, kept as is
        text = api.output_text(content) or str(step.get("error") or "")
        items.append(Item(line, 0, "output", "tool", language.redact(text), ts,
                          error=step.get("status") == "ERROR" or bool(step.get("error"))))
    elif kind == "CHECKPOINT":
        items.append(Item(line, 0, "event", "system", "compacted: the conversation was summarized here", ts,
                          tool="compacted"))
    elif kind == "ERROR_MESSAGE":
        items.append(Item(line, 0, "event", "system", language.redact(f"error: {step.get('error') or content}"), ts,
                          tool="error", error=True))
    elif kind == "SYSTEM_MESSAGE" and not said:     # hook injections and other harness text
        items.append(Item(line, 0, "event", "system", language.redact(api.system_text(content)), ts, tool="system"))
    return items


def items_of(source: str, backend, record: dict, line: int, questions: set | None = None) -> list[Item]:
    """Items of one transcript record of any source."""
    api, language = backend(source), backend("claude")
    if source == "claude":
        return claude_items(api, record, line, questions)
    if source == "codex":
        return codex_items(api, language, record, line)
    return agy_items(api, language, record, line)


# ---------------------------------------------------------------------------- transcripts
@dataclass
class Transcript:
    source: str
    session: str              # Claude session uuid / subagent stem, Codex session id, agy conversation id
    path: Path
    parent: str = ""          # a Claude subagent's parent session, an agy subagent's parent conversation

    def items(self, backend) -> list[Item]:
        return self.window(backend, 1, None)

    def attribute(self, found: list[Item]) -> list[Item]:
        """In a subagent transcript the 'user' is the parent agent, never the person."""
        if self.parent:
            for item in found:
                if item.kind == "message" and item.role == "user":
                    item.role = "peer"
        return found

    def lines(self) -> int:
        count = 0
        with self.path.open("rb") as handle:
            while chunk := handle.read(1 << 23):
                count += chunk.count(b"\n")
        return count

    def window(self, backend, first: int, last: int | None) -> list[Item]:
        """Items of physical lines first..last (1-based, inclusive; None = to the end). Lines before
        `first` are skipped by counting newlines, never parsed, so a window costs its own lines."""
        language = backend("claude")
        out: list[Item] = []
        questions: set = set()
        with self.path.open("rb") as handle:
            line, buffered = 1, b""
            while line < first:
                chunk = handle.read(1 << 23)
                if not chunk:
                    return out
                newlines = chunk.count(b"\n")
                if line + newlines < first:
                    line += newlines
                    continue
                cut = -1
                for _ in range(first - line):
                    cut = chunk.index(b"\n", cut + 1)
                buffered, line = chunk[cut + 1:], first
            handle.seek(handle.tell() - len(buffered))
            for raw_line in handle:
                if last is not None and line > last:
                    break
                if len(raw_line) <= language.HUGE_LINE * 4:
                    try:
                        rec = json.loads(raw_line)
                    except ValueError:
                        rec = None
                    if isinstance(rec, dict):
                        out.extend(self.attribute(items_of(self.source, backend, rec, line, questions)))
                line += 1
        return out

    def around(self, backend, line: int, accept, before: int, after: int) -> list[Item]:
        """Items near `line`, widening the window until `before`/`after` accepted items fit or the
        file ends; the anchor's own items are always included."""
        span, total = 400, None
        while True:
            found = self.window(backend, max(1, line - span), line + span)
            ahead = [i for i in found if i.line < line and accept(i)]
            behind = [i for i in found if i.line > line and accept(i)]
            total = total or self.lines()
            if (len(ahead) >= before or line - span <= 1) and (len(behind) >= after or line + span >= total):
                return found
            span *= 4

    def tail(self, backend, want: int, accept) -> list[Item]:
        """The last `want` accepted items (all of them when want is 0)."""
        if not want:
            return [i for i in self.items(backend) if accept(i)]
        total, span = self.lines(), 400
        while True:
            start = max(1, total - span + 1)
            found = [i for i in self.window(backend, start, None) if accept(i)]
            if len(found) >= want or start == 1:
                return found[-want:]
            span *= 4

    def head(self, backend, want: int, accept) -> list[Item]:
        span = 400
        while True:
            found = [i for i in self.window(backend, 1, span) if accept(i)]
            if len(found) >= want or span >= self.lines():
                return found[:want]
            span *= 4


def claude_root(backend) -> Path:
    return backend("claude").projects_root()


def codex_roots(backend) -> list[Path]:
    root = backend("codex").session_root()
    return [root, root.parent / "archived_sessions"]


def claude_files(backend, subagents: bool = True) -> list[Path]:
    root = claude_root(backend)
    if not root.is_dir():
        return []
    files = list(root.glob("*/*.jsonl"))
    if subagents:
        files += root.glob("*/*/subagents/*.jsonl")
    return files


def codex_files(backend) -> list[Path]:
    return [p for root in codex_roots(backend) if root.is_dir() for p in root.rglob("*.jsonl")]


_CODEX_ID = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")


def transcript_of(backend, source: str, path: Path) -> Transcript:
    if source == "agy":                # brain/<conversation>/.system_generated/logs/transcript_full.jsonl
        api = backend("agy")
        session = api.session_of(path)
        return Transcript("agy", session, path, parent=api.conversations().get(session, {}).get("parent", ""))
    if source == "codex":
        found = _CODEX_ID.search(path.name)
        return Transcript("codex", found.group(1) if found else path.stem, path)
    if path.parent.name == "subagents":
        return Transcript("claude", path.stem, path, parent=path.parent.parent.name)
    return Transcript("claude", path.stem, path)


def resolve(backend, source: str, session: str) -> list[Transcript]:
    """Transcripts whose session id starts with `session` (every copy of a Codex fork/archive)."""
    if source == "agy":
        return [transcript_of(backend, "agy", p) for p in backend("agy").transcript_paths(session)]
    if source == "claude":
        root = claude_root(backend)
        paths = [] if session.startswith("agent-") else list(root.glob(f"*/{session}*.jsonl"))
        if not paths:        # a subagent: its own id, with or without the agent- prefix
            name = session if session.startswith("agent-") else f"agent-{session}"
            paths = list(root.glob(f"*/*/subagents/{name}*.jsonl"))
        return [transcript_of(backend, "claude", p) for p in paths]
    found = [transcript_of(backend, "codex", p) for p in codex_files(backend)
             if _CODEX_ID.search(p.name) and _CODEX_ID.search(p.name).group(1).startswith(session)]
    return found


def parse_ref(ref: str) -> tuple[str, str, int, int]:
    """(source, session, line, block) from `cl:SESSION:LINE[.BLOCK]`."""
    prefix, session, anchor = ref.strip().split(":", 2)
    line, _, block = anchor.partition(".")
    return SOURCE[prefix], session, int(line), int(block or 0)


def read_spill(path: str, allowed: list[Path]) -> str | None:
    """The full text of a spilled tool result, only from inside the transcript stores."""
    target = Path(path).expanduser().resolve()
    if not any(str(target).startswith(str(root.resolve()) + os.sep) for root in allowed) or not target.is_file():
        return None
    return target.read_text(errors="replace")
