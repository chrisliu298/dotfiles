"""The recall CLI end to end on synthetic Claude, Codex and agy stores (needs ripgrep for grep)."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
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
AGY = "a9a90000-0000-4000-8000-00000000000a"
AGY_CUR = "a9a90000-0000-4000-8000-00000000000c"
AGY_SUB = "a9a90000-0000-4000-8000-00000000000d"
STAMPS = "Created At: 2026-09-01T18:00:00+08:00\nCompleted At: 2026-09-01T18:00:01+08:00\n"


def step(kind, ts="2026-09-01T10:00:00Z", source="MODEL", status="DONE", **extra):
    return {"step_index": 0, "source": source, "type": kind, "status": status, "created_at": ts, **extra}


def request(text, ts="2026-09-01T10:00:00Z"):
    content = (f"<USER_REQUEST>\n{text}\n</USER_REQUEST>\n<ADDITIONAL_METADATA>\nThe current local time is: "
               "2026-09-01T18:00:00+08:00.\n</ADDITIONAL_METADATA>\n<USER_SETTINGS_CHANGE>\nThe user changed setting "
               "`Model Selection`.\n</USER_SETTINGS_CHANGE>")
    return step("USER_INPUT", ts, source="USER_EXPLICIT", content=content)


def system(body, ts="2026-09-01T10:00:00Z", source="SYSTEM"):
    return step("SYSTEM_MESSAGE", ts, source=source, content="The following is a <SYSTEM_MESSAGE> not actually sent by "
                "the user. It is provided by the system as important information to pay attention to.\n\n"
                f"<SYSTEM_MESSAGE>\n{body}\n</SYSTEM_MESSAGE>")


def pushed(sender, text, ts="2026-09-01T10:00:00Z"):
    return system(f"[Message] timestamp={ts} sender={sender} priority=MESSAGE_PRIORITY_HIGH content={text}", ts)


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
        self.write_agy()
        self.env = {**os.environ, "CLAUDE_CONFIG_DIR": str(self.root / "claude"), "CODEX_HOME": str(self.root / "codex"),
                    "AGY_RECALL_ROOT": str(self.root / "agy"), "RECALL_CACHE_DIR": str(self.root / "cache"),
                    "CLAUDE_CODE_SESSION_ID": CUR}
        for name in ("CODEX_THREAD_ID", "CODEX_RECALL_ROOT", "ANTIGRAVITY_CONVERSATION_ID"):
            self.env.pop(name, None)
        self.agy_env = dict(self.env, ANTIGRAVITY_CONVERSATION_ID=AGY_CUR)

    def write_agy(self):
        """One agy conversation with every step type, the current one, and a subagent of the first."""
        store = self.root / "agy"
        transcript = lambda conversation: store / "brain" / conversation / ".system_generated" / "logs" / "transcript_full.jsonl"  # noqa: E731
        for conversation in (AGY, AGY_CUR, AGY_SUB):
            transcript(conversation).parent.mkdir(parents=True)
        self.write(transcript(AGY), [
            system("The following system message was injected by a SessionStart hook:\nkingfisher memory index",
                   source="SYSTEM_SDK"),                                                                    # L1
            request("We decided the kingfisher export keeps CSV."),                                          # L2
            step("PLANNER_RESPONSE", "2026-09-01T10:00:05Z", content="Plotting the kingfisher now.",
                 thinking="kingfisher-thought", model="gemini", tool_calls=[
                     {"name": "run_command", "args": json.dumps({"CommandLine": "python plot_kingfisher.py --out fig.png",
                                                                 "WaitMsBeforeAsync": 5000})},
                     {"name": "read_file", "args": {"Path": "/work/app/kingfisher.md", "StartLine": 1}}]),    # L3
            step("GENERIC", "2026-09-01T10:00:06Z", content=STAMPS * 2 +
                 "Command exited with code 0.\n\nCommand output:\nsaved kingfisher score 0.917"),          # L4
            step("GENERIC", "2026-09-01T10:00:07Z", status="ERROR", error="invalid line range",
                 content=STAMPS + "Encountered error in step execution: invalid line range"),                # L5
            step("GENERIC", "2026-09-01T10:00:08Z", status="RUNNING", content="Created At: x\n"
                 f"Tool is running as a background task with task id: {AGY}/task-6"),                       # L6
            pushed("system", "[peer] agent-msg read kingfisher-note", "2026-09-01T10:00:09Z"),               # L7
            pushed(f"{AGY}/task-6", "Task finished: kingfisher plot done", "2026-09-01T10:00:10Z"),          # L8
            step("ERROR_MESSAGE", "2026-09-01T10:00:11Z", source="SYSTEM", error="API error: UNAVAILABLE"),  # L9
            step("CHECKPOINT", "2026-09-01T12:00:00Z", source="SYSTEM",
                 content="# Resuming from a compaction\nkingfisher summary"),                              # L10
            request("Later we chose parquet for the kingfisher export.", "2026-09-01T15:00:00Z"),            # L11
            step("PLANNER_RESPONSE", "2026-09-01T15:00:05Z", content="", tool_calls=[
                {"name": "run_command", "args": {"CommandLine": "agent-msg send kingfisher-peer --file note.md"}}]),  # L12
        ])
        self.write(transcript(AGY_CUR), [request("kingfisher current thought", "2026-09-02T09:00:00Z")])
        self.write(transcript(AGY_SUB), [pushed(AGY, "audit the kingfisher export"),
                                         step("PLANNER_RESPONSE", content="kingfisher audit finished OK")])
        db = sqlite3.connect(store / "conversation_summaries.db")
        db.execute("CREATE TABLE conversation_summaries(conversation_id TEXT PRIMARY KEY, title TEXT,"
                   " workspace_uris TEXT, parent_conversation_id TEXT)")
        db.executemany("INSERT INTO conversation_summaries VALUES(?,?,?,?)", [
            (AGY, "Kingfisher export", '["file:///work/app"]', ""),
            (AGY_SUB, "", '["file:///work/app"]', AGY)])
        db.commit()
        db.close()
        (store / "cache").mkdir()
        (store / "cache" / "last_conversations.json").write_text(json.dumps({"/work/cur": AGY_CUR,
                                                                             "/work/cur/sub": AGY_CUR}))

    @staticmethod
    def write(path, records):
        path.write_text("".join(json.dumps(r) + "\n" for r in records))

    def run_cli(self, *args, code=0, env=None):
        p = subprocess.run([sys.executable, str(SCRIPT), *args[:1], "--json", *args[1:]], capture_output=True, text=True,
                           env=env or self.env, cwd="/")
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

    # ------------------------------------------------------------------ agy
    def agy(self, *args, code=0):
        return self.run_cli(*args, code=code, env=self.agy_env)

    def test_agy_steps_become_items(self):
        out = self.agy("session", AGY, "--kind", "all", "--tail", "0")
        self.assertEqual(out["sources"], ["agy"])                   # an agy shell reads agy by default
        self.assertEqual(
            [(i["ref"], i["kind"], i["role"], i.get("tool", ""), i.get("error", False)) for i in out["items"]], [
                (f"ag:{AGY}:1", "event", "system", "system", False),
                (f"ag:{AGY}:2", "message", "user", "", False),
                (f"ag:{AGY}:3", "message", "assistant", "", False),
                (f"ag:{AGY}:3.1", "command", "assistant", "run_command", False),
                (f"ag:{AGY}:3.2", "command", "assistant", "read_file", False),
                (f"ag:{AGY}:4", "output", "tool", "", False),
                (f"ag:{AGY}:5", "output", "tool", "", True),
                (f"ag:{AGY}:6", "output", "tool", "", False),
                (f"ag:{AGY}:7", "message", "peer", "system", False),
                (f"ag:{AGY}:8", "message", "automated", f"{AGY}/task-6", False),
                (f"ag:{AGY}:9", "event", "system", "error", True),
                (f"ag:{AGY}:10", "event", "system", "compacted", False),
                (f"ag:{AGY}:11", "message", "user", "", False),
                (f"ag:{AGY}:12", "command", "assistant", "run_command", False)])
        text = {i["ref"]: i["text"] for i in out["items"]}
        self.assertEqual(text[f"ag:{AGY}:1"], "The following system message was injected by a SessionStart hook:\n"
                                              "kingfisher memory index")
        self.assertEqual(text[f"ag:{AGY}:2"], "We decided the kingfisher export keeps CSV.")
        self.assertEqual(text[f"ag:{AGY}:3.1"], "python plot_kingfisher.py --out fig.png")
        self.assertEqual(text[f"ag:{AGY}:3.2"], "/work/app/kingfisher.md")
        self.assertEqual(text[f"ag:{AGY}:4"], "Command exited with code 0.\n\nCommand output:\nsaved kingfisher score 0.917")
        self.assertEqual(text[f"ag:{AGY}:7"], "[peer] agent-msg read kingfisher-note")
        self.assertEqual(out["session"]["title"], "Kingfisher export")
        self.assertEqual(out["session"]["project"], "/work/app")

    def test_agy_grep_finds_commands_and_outputs_but_never_thinking(self):
        out = self.agy("grep", "agent-msg", "--kind", "command")
        self.assertEqual([(i["ref"], i["text"]) for i in out["items"]],
                         [(f"ag:{AGY}:12", "agent-msg send kingfisher-peer --file note.md")])
        self.assertEqual([i["ref"] for i in self.agy("grep", "0.917")["items"]], [f"ag:{AGY}:4"])
        self.assertEqual(self.agy("grep", "kingfisher-thought")["status"], "no_match")
        sessions = {i["session"] for i in self.agy("grep", "kingfisher", "--limit", "50")["items"]}
        self.assertEqual(sessions, {AGY, AGY_SUB})                  # the current conversation only when named
        self.assertEqual({i["session"] for i in self.agy("grep", "kingfisher", "--session", "current")["items"]},
                         {AGY_CUR})
        self.assertEqual(self.agy("grep", "kingfisher", "--project", "/nowhere")["items"], [])

    def test_agy_search_sessions_and_timeline(self):
        hits = self.agy("search", "kingfisher export")["items"]
        self.assertEqual({i["session"] for i in hits}, {AGY})       # not the current one, not the subagent
        self.assertTrue(all(i["ref"].startswith(f"ag:{AGY}:") for i in hits))
        self.assertEqual((hits[0]["title"], hits[0]["project"]), ("Kingfisher export", "/work/app"))
        self.assertEqual({i["role"] for i in self.agy("search", "kingfisher note", "--role", "peer")["items"]}, {"peer"})
        listed = {i["session"]: i for i in self.agy("sessions")["items"]}
        self.assertEqual(set(listed), {AGY, AGY_CUR})
        self.assertEqual(listed[AGY_CUR]["project"], "/work/cur")    # from last_conversations.json
        said = self.agy("timeline", "--since", "2026-09-01", "--until", "2026-09-01")["items"]
        self.assertEqual([i["text"] for i in said], ["We decided the kingfisher export keeps CSV.",
                                                     "Later we chose parquet for the kingfisher export."])

    def test_agy_refs_open_and_subagents_show_their_parent(self):
        context = self.agy("open", f"ag:{AGY}:3.1", "--before", "1", "--after", "1")["items"]
        self.assertEqual([(i["ref"], i.get("anchor", False)) for i in context],
                         [(f"ag:{AGY}:3", False), (f"ag:{AGY}:3.1", True), (f"ag:{AGY}:3.2", False)])
        for command in (["search", "kingfisher export"], ["grep", "kingfisher"], ["sessions"],
                        ["timeline", "--since", "2026-09-01"], ["session", AGY]):
            with self.subTest(command=command[0]):
                ref = self.agy(*command)["items"][0]["ref"]
                self.assertEqual(self.agy("open", ref)["status"], "ok")
        child = self.agy("session", AGY_SUB)
        self.assertEqual(child["session"]["parent"], AGY)
        self.assertEqual([(i["role"], i.get("tool")) for i in child["items"]], [("peer", AGY), ("assistant", None)])
        self.assertEqual(self.agy("session", "current")["items"][0]["text"], "kingfisher current thought")

    def test_agy_subagents_in_grep_and_children(self):
        hit = next(i for i in self.agy("grep", "audit finished")["items"])
        self.assertEqual((hit["session"], hit["parent"]), (AGY_SUB, AGY))
        self.assertNotIn(AGY_SUB, {i["session"] for i in self.agy("grep", "kingfisher", "--no-subagents")["items"]})
        named = {i["session"] for i in self.agy("grep", "kingfisher", "--session", AGY, "--limit", "50")["items"]}
        self.assertEqual(named, {AGY, AGY_SUB})
        alone = {i["session"] for i in self.agy("grep", "kingfisher", "--session", AGY, "--no-subagents")["items"]}
        self.assertEqual(alone, {AGY})
        # The lookup's own subagents echo it, like the lookup itself.
        mine = self.run_cli("grep", "kingfisher", "--limit", "50", env=dict(self.agy_env, ANTIGRAVITY_CONVERSATION_ID=AGY))
        self.assertEqual({i["session"] for i in mine["items"]}, {AGY_CUR})
        kids = [i for i in self.agy("session", AGY, "--children")["items"] if i["kind"] == "subagent"]
        self.assertEqual([(k["session"], k["parent"], k["ref"]) for k in kids], [(AGY_SUB, AGY, f"ag:{AGY_SUB}:2")])
        self.assertEqual(kids[0]["text"], "brief: audit the kingfisher export\nfinal: kingfisher audit finished OK")

    def test_sources_with_agy(self):
        self.assertEqual(self.agy("grep", "otter", "--source", "other")["sources"], ["claude", "codex"])
        self.assertEqual(self.run_cli("grep", "kingfisher", "--source", "all")["sources"], ["claude", "codex", "agy"])
        self.assertEqual(self.run_cli("grep", "kingfisher")["items"], [])            # a Claude shell reads Claude

    # ------------------------------------------------------------------ errors
    def test_dash_query_and_usage_errors_stay_parseable(self):
        self.assertNotEqual(self.run_cli("search", "--", "--heron")["status"], "usage_error")
        self.assertEqual(self.run_cli("timeline", code=2)["status"], "usage_error")
        self.assertEqual(self.run_cli("grep", "x", "--kind", "bogus", code=2)["status"], "usage_error")
        self.assertEqual(self.run_cli("open", "nonsense", code=2)["status"], "usage_error")


if __name__ == "__main__":
    unittest.main()
