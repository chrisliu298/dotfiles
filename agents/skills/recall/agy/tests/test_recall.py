"""The agy backend: step parsing, speaker rules and conversation metadata (the CLI suite in
shared/tests runs the same store end to end)."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "recall.py"
SPEC = importlib.util.spec_from_file_location("recall_agy_test", SCRIPT)
agy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = agy
SPEC.loader.exec_module(agy)


def system(body: str) -> dict:
    return {"type": "SYSTEM_MESSAGE", "content": "The following is a <SYSTEM_MESSAGE> not actually sent by the user."
            f"\n\n<SYSTEM_MESSAGE>\n{body}\n</SYSTEM_MESSAGE>"}


def pushed(sender: str, text: str) -> dict:
    return system(f"[Message] timestamp=2026-09-01T10:00:00Z sender={sender} priority=MESSAGE_PRIORITY_HIGH content={text}")


class StepTests(unittest.TestCase):
    def test_user_request_drops_metadata_blocks(self):
        step = {"type": "USER_INPUT", "content": "<USER_REQUEST>\n看看这个仓库\n第二行\n</USER_REQUEST>\n"
                "<ADDITIONAL_METADATA>\nThe current local time is: now.\n</ADDITIONAL_METADATA>"}
        self.assertEqual(agy.message(step), ("user", "看看这个仓库\n第二行", ""))
        self.assertIsNone(agy.message({"type": "USER_INPUT", "content": "<USER_REQUEST>\n\n</USER_REQUEST>"}))
        restart = {"type": "USER_INPUT", "content": "<USER_REQUEST>\n这个会话刚被重启（tmux-persist）\n</USER_REQUEST>"}
        self.assertEqual(agy.message(restart)[0], "automated")      # typed by a tool, not the user

    def test_pushed_messages_by_sender(self):
        conversation = "9b0d99f3-5d0c-4ff7-8681-d33c0e591807"
        cases = {("system", "[peer] agent-msg read trial-1"): "peer",
                 ("system", "[飞书回答] 用户本人回答了你"): "peer",
                 (conversation, "请运行 sleep 240"): "peer",                       # a subagent's parent
                 (f"{conversation}/task-110", 'Task id "x" finished with result:\nok'): "automated",
                 ("system", "[Notice] All your subagents and background tasks have been stopped"): "automated"}
        for (sender, text), role in cases.items():
            with self.subTest(sender=sender):
                self.assertEqual(agy.message(pushed(sender, text)), (role, text, sender))

    def test_hook_injections_and_empty_replies_are_not_messages(self):
        self.assertIsNone(agy.message(system("The following system message was injected by a SessionStart hook:\nx")))
        self.assertEqual(agy.system_text(system("hook text")["content"]), "hook text")
        quoted = "relayed: <SYSTEM_MESSAGE>\ninner\n</SYSTEM_MESSAGE>\nend"      # a body quoting the tags stays whole
        self.assertEqual(agy.system_text(system(quoted)["content"]), quoted)
        self.assertIsNone(agy.message({"type": "PLANNER_RESPONSE", "content": "  ", "thinking": "private"}))
        self.assertIsNone(agy.message({"type": "GENERIC", "content": "Created At: x\nout"}))

    def test_tool_text_and_output_stamps(self):
        self.assertEqual(agy.tool_text("run_command", json.dumps({"CommandLine": "ls -la", "WaitMsBeforeAsync": 5})),
                         "ls -la")
        self.assertEqual(agy.tool_text("run_command", {"CommandLine": "sleep 1"}), "sleep 1")
        self.assertEqual(agy.tool_text("edit_file", {"Path": "a.py", "Target": "x", "Replacement": "y"}),
                         "a.py\n--- old\nx\n+++ new\ny")
        self.assertEqual(json.loads(agy.tool_text("manage_task", '{"Action": "list"}')), {"Action": "list"})
        output = "Created At: a\nCompleted At: b\nCreated At: a\nCompleted At: b\nCommand exited with code 0."
        self.assertEqual(agy.output_text(output), "Command exited with code 0.")


class StoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = mock.patch.dict(os.environ, {"AGY_RECALL_ROOT": str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        agy._conversations.cache_clear()

    def test_conversations_from_summaries_with_workspace_fallback(self):
        db = sqlite3.connect(self.root / "conversation_summaries.db")
        db.execute("CREATE TABLE conversation_summaries(conversation_id TEXT, title TEXT, workspace_uris TEXT,"
                   " parent_conversation_id TEXT)")
        db.executemany("INSERT INTO conversation_summaries VALUES(?,?,?,?)", [
            ("a", "Training", '["file:///Users/me/My%20Repo"]', ""), ("b", "", "[]", "a")])
        db.commit()
        db.close()
        (self.root / "cache").mkdir()
        (self.root / "cache" / "last_conversations.json").write_text(json.dumps({"/w/c/deep": "c", "/w/c": "c",
                                                                                 "/w/b": "b"}))
        self.assertEqual(agy.conversations(), {
            "a": {"title": "Training", "parent": "", "project": "/Users/me/My Repo"},
            "b": {"title": "", "parent": "a", "project": "/w/b"},
            "c": {"title": "", "parent": "", "project": "/w/c"}})

    def test_unreadable_summaries_warn_and_keep_the_fallback(self):
        (self.root / "conversation_summaries.db").write_text("not a database")
        (self.root / "cache").mkdir()
        (self.root / "cache" / "last_conversations.json").write_text(json.dumps({"/w": "c"}))
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(agy.conversations(), {"c": {"title": "", "parent": "", "project": "/w"}})
        self.assertIn("agy titles, workspaces and subagent parents unavailable", err.getvalue())

    def test_missing_store_is_empty(self):
        self.assertEqual(agy.conversations(), {})
        self.assertEqual(agy.transcript_paths(), [])

    def test_file_rows_resume_and_leave_a_partial_line(self):
        path = self.root / "t.jsonl"
        user = json.dumps({"type": "USER_INPUT", "created_at": "t1", "content": "<USER_REQUEST>\nhi\n</USER_REQUEST>"})
        tool = json.dumps({"type": "GENERIC", "created_at": "t2", "content": "out"})
        path.write_text(f"{user}\n{tool}\n{user[:10]}")
        cursor = agy.new_cursor()
        self.assertEqual(agy.file_rows(path, cursor), [(1, "user", "hi", "t1")])
        self.assertEqual(cursor["line"], 2)
        with path.open("a") as handle:
            handle.write(user[10:] + "\n")
        self.assertEqual(agy.file_rows(path, cursor), [(3, "user", "hi", "t1")])

    def test_current_session_and_paths(self):
        transcript = self.root / "brain" / "abc-1" / ".system_generated" / "logs" / "transcript_full.jsonl"
        transcript.parent.mkdir(parents=True)
        transcript.write_text("")
        (self.root / "brain" / "zzz").mkdir()                  # a conversation without a transcript yet
        self.assertEqual(agy.transcript_paths(), [transcript])
        self.assertEqual(agy.transcript_paths("abc"), [transcript])
        self.assertEqual(agy.session_of(transcript), "abc-1")
        with mock.patch.dict(os.environ, {"ANTIGRAVITY_CONVERSATION_ID": "abc-1"}):
            self.assertEqual(agy.current_session_id(), "abc-1")


if __name__ == "__main__":
    unittest.main()
