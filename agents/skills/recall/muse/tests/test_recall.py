from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "recall.py"
SPEC = importlib.util.spec_from_file_location("muse_recall", SCRIPT)
assert SPEC and SPEC.loader
recall = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recall
SPEC.loader.exec_module(recall)

# 2026-10-13T02:30:14.753068Z in microseconds.
TS = 1791858614753068


def frame(seq: int, payload: dict, payload_type: str = "runtime.session") -> dict:
    return {
        "sequence": seq,
        "recorded_at": TS + seq * 1_000_000,
        "stream": {"kind": "session", "id": "sess"},
        "payload_type": payload_type,
        "payload": payload,
    }


def user_turn(seq: int, text: str) -> dict:
    return frame(seq, {"kind": "run", "run_id": "run-1", "event": {"kind": "started", "prompt": text}})


def assistant_turn(seq: int, text: str) -> dict:
    return frame(seq, {"run_id": "run-1", "event": {"kind": "assistant_message_committed", "text": text}})


class MuseRecallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "sessions"
        self.session = "22222222-2222-2222-2222-222222222222"
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for name in ("MUSE_SESSION_ID", "MUSE_THREAD_ID", "MUSE_CURRENT_SESSION_LOG"):
            os.environ.pop(name, None)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_session(self, session: str, rows: list, subdir: str = "") -> Path:
        path = self.root / "2026" / "10" / "13" / session / subdir / "session.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as handle:
            for row in rows:
                handle.write(row if isinstance(row, str) else json.dumps(row))
                handle.write("\n")
        return path

    def sample_rows(self) -> list:
        return [
            frame(1, {"workspace_root": "/tmp/project"}, "runtime.session.metadata"),
            user_turn(24, "the retry budget is three attempts"),
            frame(30, {"event": {"kind": "assistant_tool_calls_committed", "tool_calls": []}}),
            assistant_turn(40, "noted: retry budget of three attempts"),
            "not json",
            user_turn(50, "   "),
        ]

    def test_extract_turns(self):
        path = self.write_session(self.session, self.sample_rows())
        turns, stats = recall.extract_turns(path)
        self.assertEqual([t.role for t in turns], ["user", "assistant"])
        self.assertEqual(turns[0].session_id, self.session)
        self.assertEqual(turns[0].cwd, "/tmp/project")
        self.assertTrue(turns[0].timestamp.startswith("2026-10-13T02:30"))
        self.assertEqual(turns[0].item_id, "seq-24")
        self.assertEqual(stats.messages_kept, 2)
        self.assertEqual(stats.malformed_records, 1)

    def test_inventory_excludes_subagent_sessions(self):
        self.write_session(self.session, self.sample_rows())
        self.write_session(self.session, self.sample_rows(), subdir="subagent/abc")
        inventory = recall.file_inventory(self.root)
        self.assertEqual(len(inventory), 1)
        self.assertEqual(inventory[0].session_id, self.session)

    def test_current_session_id_from_env(self):
        os.environ["MUSE_SESSION_ID"] = self.session
        self.assertEqual(recall.current_session_id(), self.session)

    def test_search_and_show(self):
        self.write_session(self.session, self.sample_rows())
        result = recall.search_history(self.root, "retry budget", cwd="/tmp/project", roles="both", limit=5)
        self.assertNotEqual(result["status"], "no_match")
        hit = result["candidates"][0]
        self.assertTrue(hit["confirmation"].startswith("recall: 2026-10-13"))
        self.assertEqual(hit["locator"]["session_id"], self.session)
        shown = recall.show_context(
            self.root, self.session, hit["locator"]["item_id"], before=1, after=1, max_chars=4000
        )
        self.assertEqual(shown["status"], "ok")
        self.assertTrue(any("retry budget" in t["text"] for t in shown["turns"]))

    def test_search_excludes_current_session(self):
        self.write_session(self.session, self.sample_rows())
        os.environ["MUSE_SESSION_ID"] = self.session
        result = recall.search_history(self.root, "retry budget", cwd="/tmp/project", roles="both", limit=5)
        self.assertEqual(result["status"], "no_match")

    def test_secrets_redacted_in_output(self):
        rows = [user_turn(24, "key is sk-1234567890abcdefghijklmnop")]
        self.write_session(self.session, rows)
        turns, _ = recall.extract_turns(
            self.root / "2026" / "10" / "13" / self.session / "session.jsonl"
        )
        payload = recall.turn_json(turns[0], self.root, 1)
        self.assertNotIn("sk-1234567890", payload["excerpt"] + payload["confirmation"])


if __name__ == "__main__":
    unittest.main()
