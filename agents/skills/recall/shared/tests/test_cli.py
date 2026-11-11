"""The recall CLI end to end on synthetic Claude and Codex stores (needs ripgrep for grep)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "recall"
OLD = "aaaaaaaa-0000-4000-8000-000000000001"
CUR = "cccccccc-0000-4000-8000-000000000003"
CODEX = "01a10000-0000-7000-8000-000000000009"
CODEX_CUR = "01a10000-0000-7000-8000-00000000000c"


def user(text, ts="2026-09-01T10:00:00Z", **extra):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}, **extra}


def assistant(text=None, ts="2026-09-01T10:00:05Z", tools=()):
    blocks = ([{"type": "text", "text": text}] if text else []) + [
        {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": cmd}} for tid, cmd in tools]
    return {"type": "assistant", "timestamp": ts, "message": {"role": "assistant", "content": blocks}}


def result(tid, text, ts="2026-09-01T10:00:06Z"):
    return {"type": "user", "timestamp": ts,
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": text}]}}


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("rg"):
            raise unittest.SkipTest("ripgrep not installed")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / "claude" / "projects" / "-work-app"
        self.project.mkdir(parents=True)
        spill = self.project / OLD / "tool-results" / "b1.txt"
        spill.parent.mkdir(parents=True)
        self.spill_text = "".join(f"log line {n}: heron-spill-token step {n * 7}\n" for n in range(300))
        spill.write_text(self.spill_text)
        self.write(self.project / f"{OLD}.jsonl", [
            {"type": "mode", "mode": "normal"},
            user("We decided the heron export keeps CSV."),                                       # L2
            assistant("Plotting now.", tools=[("t1", "python plot_heron.py --out fig-heron.png")]),  # L3
            result("t1", "saved fig-heron.png score 0.685"),                                        # L4
            assistant(tools=[("t2", 'cat big.log | grep "heron row"')]),                             # L5
            result("t2", f"<persisted-output>\nOutput too large (10KB). Full output saved to: {spill}\n\n"
                         "Preview (first 2KB):\nAAAA\n</persisted-output>"),                         # L6
            user("Another Claude session sent a message: heron peer note", origin={"kind": "peer"}),  # L7
            assistant("Heron work done.", ts="2026-09-01T10:01:00Z"),                                # L8
            {"type": "ai-title", "aiTitle": "Heron export"},                                         # L9
            user("This session is being continued from a previous conversation.", isCompactSummary=True,
                 ts="2026-09-01T12:00:00Z"),                                                          # L10
            user("Later we chose parquet for the heron export.", ts="2026-09-01T15:00:00Z"),         # L11
        ])
        child = self.project / OLD / "subagents" / "agent-abc123.jsonl"
        child.parent.mkdir(parents=True)
        self.write(child, [user("audit the heron export"), assistant("heron audit finished OK")])
        child.with_suffix(".meta.json").write_text(json.dumps({"agentType": "general-purpose",
                                                               "description": "Audit heron"}))
        self.write(self.project / f"{CUR}.jsonl", [
            {"type": "mode", "mode": "normal"},
            user("heron current thought", ts="2026-09-02T09:00:00Z"),
            assistant(tools=[("t9", "recall grep heron")], ts="2026-09-02T09:00:01Z"),
            result("t9", "⟦recall⟧ grep · claude · ok · heron", ts="2026-09-02T09:00:02Z"),
        ])
        codex = self.root / "codex" / "sessions" / "2026" / "09" / "01" / f"rollout-2026-09-01T00-00-00-{CODEX}.jsonl"
        codex.parent.mkdir(parents=True)
        self.write(codex, [
            {"type": "session_meta", "timestamp": "2026-09-01T00:00:00Z",
             "payload": {"id": CODEX, "cwd": "/work/app", "source": "cli"}},
            {"type": "response_item", "timestamp": "2026-09-01T00:00:01Z",
             "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "trim the otter logs"}]}},
            {"type": "response_item", "timestamp": "2026-09-01T00:00:02Z",
             "payload": {"type": "function_call", "name": "exec_command", "call_id": "c1",
                         "arguments": json.dumps({"cmd": "truncate -s 0 otter.log"})}},
            {"type": "response_item", "timestamp": "2026-09-01T00:00:03Z",
             "payload": {"type": "function_call_output", "call_id": "c1", "output": "otter.log emptied"}},
            {"type": "response_item", "timestamp": "2026-09-01T00:00:04Z",
             "payload": {"type": "agent_message", "author": "/root/otter_review", "recipient": "/root",
                         "content": [{"type": "input_text", "text": "otter review: the only blocker is resolved"}]}},
            {"type": "event_msg", "timestamp": "2026-09-01T00:00:05Z",
             "payload": {"type": "turn_aborted", "reason": "interrupted"}},
        ])
        mine = codex.parent / f"rollout-2026-09-01T01-00-00-{CODEX_CUR}.jsonl"
        self.write(mine, [
            {"type": "session_meta", "timestamp": "2026-09-01T01:00:00Z",
             "payload": {"id": CODEX_CUR, "cwd": "/work/app", "source": "cli"}},
            {"type": "response_item", "timestamp": "2026-09-01T01:00:01Z",
             "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "otter again"}]}},
        ])
        self.env = {**os.environ, "CLAUDE_CONFIG_DIR": str(self.root / "claude"), "CODEX_HOME": str(self.root / "codex"),
                    "RECALL_CACHE_DIR": str(self.root / "cache"), "CLAUDE_CODE_SESSION_ID": CUR}
        self.env.pop("CODEX_THREAD_ID", None)
        self.env.pop("CODEX_RECALL_ROOT", None)

    @staticmethod
    def write(path, records):
        path.write_text("".join(json.dumps(r) + "\n" for r in records))

    def run_cli(self, *args, code=0):
        p = subprocess.run([sys.executable, str(SCRIPT), *args[:1], "--json", *args[1:]], capture_output=True, text=True,
                           env=self.env, cwd="/")
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(out["schema"], "recall/2")
        self.assertIsInstance(out["items"], list)
        return out

    # ------------------------------------------------------------------ grep
    def test_grep_reaches_commands_outputs_subagents_and_spills(self):
        out = self.run_cli("grep", "heron", "--limit", "50")
        found = {(i["session"], i["kind"]) for i in out["items"]}
        self.assertIn((OLD, "command"), found)
        self.assertIn((OLD, "message"), found)
        self.assertIn(("agent-abc123", "message"), found)
        self.assertTrue(any(":spill:" in i["ref"] for i in out["items"]))
        self.assertNotIn(CUR, {i["session"] for i in out["items"]})      # the lookup's own session
        number = self.run_cli("grep", "0.685")["items"]
        self.assertEqual([(i["kind"], i["ref"]) for i in number], [("output", f"cl:{OLD}:4")])

    def test_grep_current_session_only_when_named_and_never_its_echoes(self):
        out = self.run_cli("grep", "heron", "--session", "current")
        self.assertEqual([i["text"] for i in out["items"]], ["heron current thought"])

    def test_grep_codex_commands_and_outputs(self):
        out = self.run_cli("grep", "otter", "--source", "codex", "--session", CODEX)
        self.assertEqual(sorted((i["kind"], i["role"]) for i in out["items"]),
                         [("command", "assistant"), ("message", "peer"), ("message", "user"), ("output", "tool")])
        command = next(i for i in out["items"] if i["kind"] == "command")
        self.assertEqual(command["text"], "truncate -s 0 otter.log")
        self.assertTrue(command["ref"].startswith(f"cx:{CODEX}:"))

    # ------------------------------------------------------------------ open
    def test_open_context_and_full_spilled_output_pages(self):
        context = self.run_cli("open", f"cl:{OLD}:2", "--after", "2")
        self.assertEqual([(i["kind"], i.get("anchor", False)) for i in context["items"]],
                         [("message", True), ("message", False), ("command", False)])
        page = self.run_cli("open", f"cl:{OLD}:6", "--full", "--max-chars", "6000")
        self.assertEqual(len(page["items"][0]["text"]), 6000)
        self.assertEqual(page["next_cursor"], 6000)
        rest = self.run_cli("open", f"cl:{OLD}:6", "--full", "--cursor", "6000", "--max-chars", "20000")
        self.assertEqual(page["items"][0]["text"] + rest["items"][0]["text"], self.spill_text)
        self.assertIsNone(rest["next_cursor"])

    def test_refs_from_every_command_open(self):
        for command in (["grep", "heron"], ["search", "heron export"], ["timeline", "--since", "2026-09-01"],
                        ["session", OLD], ["sessions"]):
            with self.subTest(command=command[0]):
                ref = self.run_cli(*command)["items"][0]["ref"]
                self.assertEqual(self.run_cli("open", ref)["status"], "ok")

    # ------------------------------------------------------------------ session
    def test_session_tail_head_and_children(self):
        tail = self.run_cli("session", OLD[:8], "--tail", "2")
        self.assertEqual([i["role"] for i in tail["items"]], ["assistant", "user"])
        self.assertEqual(tail["session"]["title"], None)          # not indexed yet: no transcript scan
        head = self.run_cli("session", OLD[:8], "--head", "1", "--kind", "all")
        self.assertEqual(head["items"][0]["text"], "We decided the heron export keeps CSV.")
        kids = [i for i in self.run_cli("session", OLD, "--children")["items"] if i["kind"] == "subagent"]
        self.assertIn("final: heron audit finished OK", kids[0]["text"])
        self.assertIn("Audit heron", kids[0]["tool"])
        brief = self.run_cli("open", kids[0]["ref"], "--before", "1", "--after", "0")["items"][0]
        self.assertEqual((brief["role"], brief["text"]), ("peer", "audit the heron export"))   # the parent's brief
        self.assertEqual(self.run_cli("session", "current")["items"][0]["text"], "heron current thought")

    # ------------------------------------------------------------------ search / timeline / sessions
    def test_search_needs_current_named_and_keeps_peers_out_of_user(self):
        self.assertNotIn(CUR, {i["session"] for i in self.run_cli("search", "heron current thought")["items"]})
        named = self.run_cli("search", "heron current thought", "--session", "current")["items"]
        self.assertEqual({i["session"] for i in named}, {CUR})
        roles = {i["role"] for i in self.run_cli("search", "heron peer note", "--role", "user")["items"]}
        self.assertNotIn("peer", roles)

    def test_timeline_and_sessions(self):
        said = self.run_cli("timeline", "--since", "2026-09-01", "--until", "2026-09-02T00:00")["items"]
        self.assertEqual([i["text"] for i in said if i["session"] == OLD],
                         ["We decided the heron export keeps CSV.", "Later we chose parquet for the heron export."])
        self.assertEqual([i["session"] for i in self.run_cli("sessions", "--query", "heron export")["items"]], [OLD])
        self.assertEqual(self.run_cli("sessions", "--query", "her")["items"], [])     # whole words only

    def test_grep_matches_text_that_json_escapes(self):
        out = self.run_cli("grep", 'grep "heron row"', "--kind", "command")
        self.assertEqual([i["ref"] for i in out["items"]], [f"cl:{OLD}:5"])

    def test_scope_filters_hold_for_every_hit(self):
        self.assertEqual(self.run_cli("grep", "heron-spill-token", "--project", "/nowhere")["items"], [])
        env = dict(self.env, CODEX_THREAD_ID=CODEX_CUR)
        env.pop("CLAUDE_CODE_SESSION_ID")
        p = subprocess.run([sys.executable, str(SCRIPT), "grep", "--json", "otter"], capture_output=True, text=True, env=env)
        self.assertNotIn(CODEX_CUR, {i["session"] for i in json.loads(p.stdout)["items"]})
        # 10:00Z and 15:00Z are both on 2026-09-01 here; a time bound must split them, a date bound can't.
        bound = datetime.fromisoformat("2026-09-01T12:00:00+00:00").astimezone().strftime("%Y-%m-%dT%H:%M")
        early = " ".join(i["text"] for i in self.run_cli("search", "heron export", "--until", bound)["items"])
        self.assertIn("CSV", early)
        self.assertNotIn("parquet", early)

    def test_events_and_codex_peer_messages(self):
        events = self.run_cli("session", CODEX, "--source", "codex", "--kind", "event")["items"]
        self.assertEqual([i["text"] for i in events], ["turn_aborted: interrupted"])
        compacted = self.run_cli("session", OLD, "--kind", "event")["items"]
        self.assertEqual([i["ref"] for i in compacted], [f"cl:{OLD}:10"])
        peer = self.run_cli("search", "only blocker resolved", "--source", "codex")["items"]
        self.assertEqual([i["role"] for i in peer], ["peer"])

    def test_unknown_refs_are_not_found(self):
        self.assertEqual(self.run_cli("open", f"cl:{OLD}:3.9")["status"], "not_found")
        self.assertEqual(self.run_cli("open", f"cl:{OLD}:9")["status"], "not_found")

    # ------------------------------------------------------------------ errors
    def test_dash_query_and_usage_errors_stay_parseable(self):
        self.assertNotEqual(self.run_cli("search", "--", "--heron")["status"], "usage_error")
        self.assertEqual(self.run_cli("timeline", code=2)["status"], "usage_error")
        self.assertEqual(self.run_cli("grep", "x", "--kind", "bogus", code=2)["status"], "usage_error")
        self.assertEqual(self.run_cli("open", "nonsense", code=2)["status"], "usage_error")


if __name__ == "__main__":
    unittest.main()
