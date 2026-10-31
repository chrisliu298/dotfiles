"""The persistent index follows appends, rewrites and deletions of real transcript files."""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

PATH = Path(__file__).resolve().parents[1] / "retrieve.py"
SPEC = importlib.util.spec_from_file_location("retrieve_index_test", PATH)
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def claude_record(role, text, ts="2026-09-01T10:00:00Z"):
    content = text if role == "user" else [{"type": "text", "text": text}]
    return {"type": role, "timestamp": ts, "cwd": "/work/app", "isSidechain": False,
            "message": {"role": role, "content": content}}


def codex_record(item, role, text, ordinal):
    kind = "input_text" if role == "user" else "output_text"
    return {"timestamp": f"2026-09-09T10:00:0{ordinal}Z", "ordinal": ordinal, "type": "response_item",
            "payload": {"id": item, "type": "message", "role": role, "content": [{"type": kind, "text": text}]}}


class IndexTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = mock.patch.dict(os.environ, {"RECALL_CACHE_DIR": str(self.root / "cache"),
                                          "CLAUDE_CONFIG_DIR": str(self.root / "claude"),
                                          "CODEX_RECALL_ROOT": str(self.root / "codex" / "sessions")})
        env.start()
        self.addCleanup(env.stop)
        for name in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID"):
            os.environ.pop(name, None)

    def sessions(self, source, query):
        result = r.search(source, [query], str(self.root), 5, "both")
        return [c["session"] for c in result["candidates"]]

    def write(self, path, records, mode="w"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open(mode) as handle:
            handle.writelines(json.dumps(record) + "\n" for record in records)

    def test_claude_append_rewrite_and_delete(self):
        path = self.root / "claude" / "projects" / "app" / "s1.jsonl"
        self.write(path, [{"type": "mode", "mode": "normal"}, claude_record("user", "orchard websocket")])
        self.assertEqual(self.sessions("claude", "orchard websocket"), ["s1"])
        self.write(path, [claude_record("assistant", "zeppelin hangar ready")], "a")
        self.assertEqual(self.sessions("claude", "zeppelin hangar"), ["s1"])
        self.write(path, [claude_record("user", "orchard zeppelin again")], "a")     # merges into existing postings
        result = r.search("claude", ["orchard zeppelin"], str(self.root), 5, "both")
        self.assertEqual([e["line"] for e in result["candidates"][0]["evidence"]], [4])
        db = sqlite3.connect(self.root / "cache" / "index" / "claude.sqlite")
        self.assertEqual(db.execute("SELECT count(*) FROM files").fetchone()[0], 1)   # updated in place
        self.write(path, [{"type": "mode", "mode": "normal"}, claude_record("user", "quartz lantern")])
        self.assertEqual(self.sessions("claude", "zeppelin hangar"), [])               # rewrite re-indexed
        self.assertEqual(self.sessions("claude", "quartz lantern"), ["s1"])
        path.unlink()
        self.assertEqual(self.sessions("claude", "quartz lantern"), [])
        self.assertEqual(db.execute("SELECT count(*) FROM postings").fetchone()[0], 0)

    def test_codex_append_keeps_session_metadata(self):
        path = self.root / "codex" / "sessions" / "2026" / "09" / "09" / "rollout-a.jsonl"
        meta = {"timestamp": "2026-09-09T10:00:00Z", "type": "session_meta",
                "payload": {"id": "sess-a", "cwd": "/work/app", "thread_source": "user"}}
        self.write(path, [meta, codex_record("m1", "user", "orchard websocket", 1)])
        self.assertEqual(self.sessions("codex", "orchard websocket"), ["sess-a"])
        self.write(path, [codex_record("m2", "assistant", "zeppelin hangar", 2)], "a")
        result = r.search("codex", ["zeppelin hangar"], str(self.root), 5, "both")
        self.assertEqual(result["candidates"][0]["cwd"], "/work/app")
        self.assertEqual(result["stats"]["messages_kept"], 2)

    def test_claude_dates_are_local_not_utc(self):
        with mock.patch.dict(os.environ, {"TZ": "Asia/Shanghai"}):
            time.tzset()
            self.addCleanup(time.tzset)
            path = self.root / "claude" / "projects" / "app" / "s1.jsonl"
            self.write(path, [{"type": "mode", "mode": "normal"},
                              claude_record("user", "orchard websocket", "2026-10-30T23:30:00Z")])
            found = r.search("claude", ["orchard websocket"], str(self.root), 5, "both", since="2026-10-31")
        self.assertEqual([c["session"] for c in found["candidates"]], ["s1"])

    def test_codex_dates_are_local_not_utc(self):
        with mock.patch.dict(os.environ, {"TZ": "Asia/Shanghai"}):
            time.tzset()
            self.addCleanup(time.tzset)
            path = self.root / "codex" / "sessions" / "2026" / "10" / "31" / "rollout-a.jsonl"
            meta = {"timestamp": "2026-10-30T23:30:00Z", "type": "session_meta",
                    "payload": {"id": "sess-a", "cwd": "/work/app", "thread_source": "user"}}
            record = codex_record("m1", "user", "orchard websocket", 1)
            record["timestamp"] = "2026-10-30T23:30:00Z"
            self.write(path, [meta, record])
            found = r.search("codex", ["orchard websocket"], str(self.root), 5, "both", since="2026-10-31")
        self.assertEqual([c["session"] for c in found["candidates"]], ["sess-a"])

    def test_timeline_keeps_tokenless_replies_current_session_and_drops_system_turns(self):
        path = self.root / "claude" / "projects" / "app" / "s1.jsonl"
        scheduled = dict(claude_record("user", "scheduled tick"), isMeta=True, promptSource="system")
        self.write(path, [{"type": "mode", "mode": "normal"}, claude_record("user", "go"), scheduled])
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "s1"}):
            found = r.timeline("claude", str(self.root), 0)
        self.assertEqual([m["text"] for m in found["sessions"][0]["messages"]], ["go"])
        self.assertEqual(found["coverage"]["messages_filtered"], 1)
        self.assertEqual(found["current_task_exclusion"], "included")

    def test_timezone_change_rebuilds_local_dates(self):
        path = self.root / "claude" / "projects" / "app" / "s1.jsonl"
        self.write(path, [{"type": "mode", "mode": "normal"},
                          claude_record("user", "orchard websocket", "2026-10-30T23:30:00Z")])
        self.addCleanup(time.tzset)
        for zone, day, hits in (("Asia/Shanghai", "2026-10-31", ["s1"]), ("UTC", "2026-10-31", [])):
            with mock.patch.dict(os.environ, {"TZ": zone}):
                time.tzset()
                found = r.search("claude", ["orchard websocket"], str(self.root), 5, "both", since=day)
            self.assertEqual([c["session"] for c in found["candidates"]], hits)

    def test_timeline_lists_window_without_a_query(self):
        path = self.root / "claude" / "projects" / "app" / "s1.jsonl"
        self.write(path, [{"type": "mode", "mode": "normal"},
                          claude_record("user", "too early", "2026-09-01T07:59:00Z"),
                          claude_record("user", "ship the fix", "2026-09-01T08:00:00Z"),
                          claude_record("assistant", "done", "2026-09-01T08:01:00Z"),
                          claude_record("user", "too late", "2026-09-01T12:01:00Z")])
        since = datetime(2026, 9, 1, 8, tzinfo=timezone.utc).timestamp()
        until = datetime(2026, 9, 1, 12, tzinfo=timezone.utc).timestamp()
        found = r.timeline("claude", str(self.root), since, until)
        self.assertEqual(found["status"], "ok")
        session = found["sessions"][0]
        self.assertEqual(session["session"], "s1")
        self.assertEqual([(m["line"], m["text"]) for m in session["messages"]], [(3, "ship the fix")])
        both = r.timeline("claude", str(self.root), since, until, roles="both")
        self.assertEqual(both["coverage"]["messages_listed"], 2)


if __name__ == "__main__":
    unittest.main()
