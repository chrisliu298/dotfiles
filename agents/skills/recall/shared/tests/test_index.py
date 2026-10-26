"""The persistent index follows appends, rewrites and deletions of real transcript files."""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
