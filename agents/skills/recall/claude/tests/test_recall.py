"""Hermetic tests for recall.py — synthetic Claude transcripts in a temp CLAUDE_CONFIG_DIR.

Run: uv run python -m unittest discover -s agents/skills/recall/claude/tests   (or: uv run --with pytest pytest <dir>)
Never touches the real ~/.claude store or depends on the invoking session's env.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "recall.py"
SPEC = importlib.util.spec_from_file_location("recall", SCRIPT)
recall = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recall
SPEC.loader.exec_module(recall)

CONFIRMATION = re.compile(r"^recall: \d{4}-\d{2}-\d{2} · [0-9a-f]{8} · \S")
S_OLD = "aaaaaaaa-0000-0000-0000-000000000001"
S_NEW = "bbbbbbbb-0000-0000-0000-000000000002"
S_CUR = "cccccccc-0000-0000-0000-000000000003"
S_RELAY = "dddddddd-0000-0000-0000-000000000004"
S_OTHER = "eeeeeeee-0000-0000-0000-000000000005"


def user(text, ts="2026-09-01T10:00:00Z", **extra):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}, **extra}


def assistant(text, ts="2026-09-01T10:00:05Z", **extra):
    return {"type": "assistant", "timestamp": ts,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}, **extra}


def tool_result(text, ts="2026-09-01T10:00:03Z"):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": text}]}}


class RecallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cwd = str(self.root / "work" / "app.repo")
        self.other_cwd = str(self.root / "work" / "other")
        env = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.root / "claude")})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        self.clock = time.time() - 10_000

    # ------------------------------------------------------------------ fixtures
    def write(self, session, records, *, cwd=None, interactive=True):
        cwd = cwd or self.cwd
        d = self.root / "claude" / "projects" / recall.encode_cwd(cwd)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{session}.jsonl"
        head = [{"type": "mode", "mode": "normal", "sessionId": session}] if interactive \
            else [{"type": "queue-operation", "operation": "enqueue"}]
        with path.open("w") as fh:
            for rec in head + records:
                if rec.get("type") in ("user", "assistant"):
                    rec = {"cwd": cwd, "sessionId": session, "isSidechain": False, **rec}
                fh.write(json.dumps(rec) + "\n")
        self.clock += 100                              # later writes are newer sessions
        os.utime(path, (self.clock, self.clock))
        return path

    def cli(self, *args, env=None):
        run_env = {**os.environ, **(env or {})}
        p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                           env=run_env)
        out = json.loads(p.stdout) if p.stdout.strip().startswith("{") else p.stdout
        return p.returncode, out

    def search(self, q, *extra, env=None):
        return self.cli("search", "--cwd", self.cwd, "--q", q, *extra, env=env)

    def standard_store(self):
        self.write(S_OLD, [
            user("Let's cap the auth retry at 4 attempts with exponential backoff."),
            assistant("Sounds good, updating the client config now."),
            user("Also the staging server runs on port 8443."),
        ])
        self.write(S_NEW, [
            user("Unrelated: please tidy the zsh prompt colors."),
            assistant("Done, prompt colors updated."),
        ])

    def test_role_filter_applies_before_candidate_limit(self):
        self.write(S_OLD, [
            assistant("quartz retries"),
            user("We decided the quartz service retries at most four times with a delay."),
        ])
        _, out = self.search("quartz retries", "--roles", "user", "--k", "1")
        self.assertEqual(len(out["candidates"]), 1)
        self.assertEqual(out["candidates"][0]["role"], "user")

    # ------------------------------------------------------------------ search statuses
    def test_confident_hit_prints_contract_confirmation(self):
        self.standard_store()
        rc, out = self.search("what did we decide about the auth retry cap")
        self.assertEqual((rc, out["status"]), (0, "confident"))
        self.assertRegex(out["confirmation"], CONFIRMATION)
        self.assertIn("aaaaaaaa", out["confirmation"])
        top = out["candidates"][0]
        self.assertEqual((top["role"], top["session"], top["project"]), ("user", S_OLD, self.cwd))
        self.assertIn("4 attempts", top["gist"])
        self.assertEqual(top["confirmation"], out["confirmation"])

    def test_empty_query_after_boilerplate(self):
        self.standard_store()
        rc, out = self.search("what did we decide about")
        self.assertEqual((rc, out["status"]), (12, "empty_query"))
        self.assertIn("reason", out)
        self.assertEqual(out["candidates"], [])

    def test_no_match_never_invents_and_suggests_escalation(self):
        self.standard_store()
        rc, out = self.search("quarterly sourdough fermentation schedule")
        self.assertEqual((rc, out["status"]), (13, "no_match"))
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["escalate"], "--scope all")
        self.assertNotIn("confirmation", out)

    def test_ambiguous_between_near_identical_statements(self):
        self.write(S_OLD, [user("We settled the upload chunk size at 8 MB for the uploader.")])
        self.write(S_NEW, [user("We settled the upload chunk size at 16 MB for the uploader.")])
        rc, out = self.search("upload chunk size")
        self.assertEqual((rc, out["status"]), (11, "ambiguous"))
        self.assertNotIn("confirmation", out)            # only a confident hit is silent-loaded
        self.assertGreaterEqual(len(out["candidates"]), 2)
        for c in out["candidates"]:
            self.assertRegex(c["confirmation"], CONFIRMATION)

    def test_assistant_only_hit_is_capped_and_flagged(self):
        self.write(S_OLD, [user("ok"), assistant("I propose the cache eviction TTL be 90 seconds.")])
        rc, out = self.search("cache eviction TTL")
        self.assertEqual(out["status"], "ambiguous")
        self.assertIn("agent turn, unconfirmed", out["candidates"][0]["confirmation"])

    def test_question_top_hit_is_not_confident(self):
        self.write(S_OLD, [user("Should the sync daemon poll interval be 30 seconds?")])
        rc, out = self.search("sync daemon poll interval")
        self.assertEqual((rc, out["status"]), (11, "ambiguous"))
        self.assertEqual(out["candidates"][0]["kind"], "question")
        self.assertIn("you asked", out["candidates"][0]["confirmation"])

    def test_decision_cue_inside_question_is_still_question(self):
        self.write(S_OLD, [user("Should we prefer redis for the session cache backend?")])
        rc, out = self.search("redis session cache backend")
        self.assertEqual(out["status"], "ambiguous")
        self.assertEqual(out["candidates"][0]["kind"], "question")

    def test_question_kind_unit(self):
        self.assertTrue(recall.is_question("Should we choose X?"))
        self.assertTrue(recall.is_question("Thoughts on the cache. Do we prefer redis?"))
        self.assertTrue(recall.is_question("缓存用 redis 吗？"))
        self.assertFalse(recall.is_question("We decided on redis. Any objections?"))
        self.assertFalse(recall.is_question("Use redis? No — we chose memcached."))

    def test_statement_top_hit_is_marked_statement(self):
        self.standard_store()
        rc, out = self.search("auth retry cap")
        self.assertEqual(out["candidates"][0]["kind"], "statement")

    def test_single_concept_overlap_does_not_mask_real_match(self):
        # 'goal-loop' repeated scores high on BM25 but is one concept; the real answer covers more.
        self.write(S_OLD, [user("The goal-loop auto mode is gated on the oracle turning red.")])
        self.write(S_NEW, [user("goal-loop goal-loop goal-loop is a meta loop around goal-loop.")])
        rc, out = self.search("goal-loop auto mode gating")
        self.assertNotEqual(out["status"], "no_match")
        self.assertIn("oracle", out["candidates"][0]["gist"])

    def test_cjk_query(self):
        self.write(S_OLD, [user("帮我完全卸载微信输入法")])
        rc, out = self.search("卸载微信输入法")
        self.assertIn(out["status"], ("confident", "ambiguous"))
        self.assertIn("微信", out["candidates"][0]["gist"])

    # ------------------------------------------------------------------ scope & filtering
    def test_current_session_excluded_by_default(self):
        self.write(S_CUR, [user("The deploy freeze window starts Friday 5pm.")])
        env = {"CLAUDE_CODE_SESSION_ID": S_CUR}
        rc, out = self.search("deploy freeze window", env=env)
        self.assertEqual(out["status"], "no_match")
        self.assertEqual(out["stats"]["excluded_current"], 1)
        rc, out = self.search("deploy freeze window", "--include-current", env=env)
        self.assertEqual(out["candidates"][0]["session"], S_CUR)

    def test_headless_sessions_excluded_unless_requested(self):
        self.write(S_RELAY, [user("Relay body: the vendor webhook secret rotates monthly.")],
                   interactive=False)
        rc, out = self.search("vendor webhook rotates monthly")
        self.assertEqual(out["status"], "no_match")
        rc, out = self.search("vendor webhook rotates monthly", "--include-headless")
        self.assertEqual(out["candidates"][0]["session"], S_RELAY)

    def test_noise_turns_are_not_searchable(self):
        self.write(S_OLD, [
            user("<task-notification>\n<task-id>x</task-id> zebra quantum finished</task-notification>"),
            user("<command-message>push</command-message>\n<command-name>/push</command-name> zebra quantum"),
            user("Base directory for this skill: /x zebra quantum"),
            user("This session is being continued from a previous conversation. zebra quantum",
                 isCompactSummary=True),
            user("zebra quantum from a subagent", isSidechain=True),
            tool_result("zebra quantum tool output"),
        ])
        rc, out = self.search("zebra quantum")
        self.assertEqual(out["status"], "no_match")

    def test_scope_all_searches_other_projects(self):
        self.standard_store()
        self.write(S_OTHER, [user("For the billing service we pinned postgres to 16.4.")],
                   cwd=self.other_cwd)
        rc, out = self.search("billing postgres pinned")
        self.assertEqual(out["status"], "no_match")
        self.assertEqual(out["escalate"], "--scope all")
        rc, out = self.search("billing postgres pinned", "--scope", "all")
        self.assertEqual(out["status"], "confident")
        self.assertEqual(out["candidates"][0]["project"], self.other_cwd)
        self.assertEqual(out["stats"]["scope"], "all")

    def test_recency_window_truncation_suggests_full_scan(self):
        self.write(S_OLD, [user("The nightly backup bucket lives in us-west-2.")])
        self.write(S_NEW, [user("filler about prompt colors")])
        rc, out = self.search("nightly backup bucket", "--max-files", "1")
        self.assertEqual(out["status"], "no_match")
        self.assertTrue(out["stats"]["truncated"])
        self.assertEqual(out["escalate"], "--max-files 0")
        rc, out = self.search("nightly backup bucket", "--max-files", "0")
        self.assertEqual(out["candidates"][0]["session"], S_OLD)

    # ------------------------------------------------------------------ redaction
    def test_secrets_redacted_in_search_and_show(self):
        secret = "sk-" + "A1b2C3d4E5f6G7h8I9j0"
        self.write(S_OLD, [
            user(f"The billing webhook config: OPENAI key {secret}, "
                 "header bearer abcdefghijklmnopqrstuv, DB_PASSWORD=hunter2hunter2, "
                 '"API_KEY": "zzzzyyyyxxxx"'),
            user("-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY----- billing webhook key"),
        ])
        rc, out = self.search("billing webhook config")
        blob = json.dumps(out)
        for raw in (secret, "abcdefghijklmnopqrstuv", "hunter2hunter2", "zzzzyyyyxxxx", "MIIE"):
            self.assertNotIn(raw, blob)
        self.assertIn("[REDACTED:openai-key]", blob)
        self.assertIn("[REDACTED:bearer]", blob)
        self.assertIn("[REDACTED:env-secret]", blob)
        self.assertGreater(out["redactions"], 0)
        c = out["candidates"][0]
        rc, shown = self.cli("show", "--cwd", self.cwd, "--session", c["session_short"],
                             "--line", str(c["line"]))
        blob = json.dumps(shown)
        self.assertEqual(shown["status"], "ok")
        for raw in (secret, "hunter2hunter2", "MIIE"):
            self.assertNotIn(raw, blob)

    def test_unterminated_private_key_redacted_to_end(self):
        text = "key follows -----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAA\nQUFBQUFB"
        out = recall.redact(text)
        self.assertEqual(out, "key follows [REDACTED:private-key]")
        self.assertIn("[REDACTED:private-key] after",
                      recall.redact("-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY----- after"))

    def test_redact_patterns_unit(self):
        cases = {
            "Authorization: Bearer abcdefghijklmnop1234": "bearer",
            "export GH=ghp_" + "a" * 30: "github-token",
            "AKIA" + "A" * 16: "aws-key",
            "data:image/png;base64," + "Q" * 100: "data-url",
            "x " + "Z9" * 300: "long-blob",
        }
        for text, label in cases.items():
            self.assertIn(f"[REDACTED:{label}]", recall.redact(text), text)

    # ------------------------------------------------------------------ show
    def test_show_returns_surrounding_turns(self):
        self.standard_store()
        rc, out = self.search("auth retry cap")
        c = out["candidates"][0]
        rc, shown = self.cli("show", "--cwd", self.cwd, "--session", c["session_short"],
                             "--line", str(c["line"]))
        self.assertEqual((rc, shown["status"], shown["session"]), (0, "ok", S_OLD))
        roles = [t["role"] for t in shown["turns"]]
        self.assertIn("assistant", roles)
        self.assertTrue(any("8443" in t["text"] for t in shown["turns"]))

    def test_show_falls_back_to_other_projects(self):
        self.write(S_OTHER, [user("For the billing service we pinned postgres to 16.4.")],
                   cwd=self.other_cwd)
        rc, shown = self.cli("show", "--cwd", self.cwd, "--session", "eeeeeeee", "--line", "2")
        self.assertEqual((shown["status"], shown["session"]), ("ok", S_OTHER))

    def test_show_ambiguous_prefix_and_missing(self):
        self.write("abcd0000-0000-0000-0000-000000000001", [user("one")])
        self.write("abcd0000-0000-0000-0000-000000000002", [user("two")])
        rc, shown = self.cli("show", "--cwd", self.cwd, "--session", "abcd0000", "--line", "2")
        self.assertEqual((rc, shown["status"]), (11, "ambiguous_session"))
        rc, shown = self.cli("show", "--cwd", self.cwd, "--session", "ffffffff", "--line", "2")
        self.assertEqual((rc, shown["status"]), (11, "not_found"))

    # ------------------------------------------------------------------ query normalization
    def test_compound_identifier_is_one_concept(self):
        cleaned, terms, groups = recall.normalize_query("which browser does claude-in-chrome attach to")
        self.assertEqual(len(groups), 3)                 # browser, claude-in-chrome, attach
        self.assertIn("chrome", terms)                   # sub-parts still reach BM25

    def test_encode_cwd(self):
        self.assertEqual(recall.encode_cwd("/Users/you/proj/.config/ghostty"),
                         "-Users-you-proj--config-ghostty")


if __name__ == "__main__":
    unittest.main()
