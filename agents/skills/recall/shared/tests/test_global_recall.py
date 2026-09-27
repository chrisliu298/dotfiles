"""Routing and source attribution for cross-agent recall."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "global_recall.py"
SPEC = importlib.util.spec_from_file_location("global_recall", SCRIPT)
recall = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recall
SPEC.loader.exec_module(recall)


def hit(source: str) -> dict:
    return {
        "status": "confident",
        "candidates": [{"role": "user", "confirmation": f"recall: 2026-09-01 · 12345678 · from {source}"}],
    }


class GlobalRecallTests(unittest.TestCase):
    def invoke(self, *args: str) -> dict:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            recall.main(["search", "--cwd", "/tmp/project", "--query", "retry cap", *args])
        return json.loads(output.getvalue())

    def test_default_reads_only_calling_agents_complete_history(self) -> None:
        for agent in ("codex", "claude"):
            with self.subTest(agent=agent), mock.patch.object(recall, "run_source", return_value=hit(agent)) as run:
                result = self.invoke("--agent", agent)
                self.assertEqual(run.call_count, 1)
                source, command = run.call_args.args
                self.assertEqual(source, agent)
                self.assertNotIn("--scope", command)  # shared worker always searches all history
                self.assertEqual(result["candidates"][0]["source"], agent)
                self.assertTrue(result["confirmation"].startswith(f"recall [{agent}]:"))

    def test_batch_queries_and_dates_reach_one_worker(self) -> None:
        with mock.patch.object(recall, "run_source", return_value=hit("codex")) as run:
            self.invoke("--agent", "codex", "--query", "retry budget", "--since", "2026-09-01")
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[1]
        self.assertEqual(command.count("--query"), 2)
        self.assertIn("2026-09-01", command)

    def test_real_worker_reads_only_requested_store(self) -> None:
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "claude" / "projects" / "demo"
            project.mkdir(parents=True)
            records = [{"type": "mode", "mode": "normal"},
                       {"type": "user", "timestamp": "2026-09-01T00:00:00Z",
                        "message": {"content": "orchard retry budget seven"}}]
            (project / "fixture.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(root / "claude"),
                                              "RECALL_CACHE_DIR": str(root / "cache")}):
                result = recall.search(["orchard retry", "retry budget"], directory, ["claude"], 5)
                self.assertEqual(result["candidates"][0]["source"], "claude")
                self.assertEqual(result["candidates"][0]["evidence"][0]["session"], "fixture")
                self.assertEqual(result["sources"]["claude"]["coverage"]["messages_searched"], 1)

    def test_other_source_is_explicit(self) -> None:
        with mock.patch.object(recall, "run_source", return_value=hit("claude")) as run:
            result = self.invoke("--agent", "codex", "--source", "other")
        self.assertEqual(run.call_args.args[0], "claude")
        self.assertEqual(result["candidates"][0]["source"], "claude")

    def test_roles_reaches_each_source_before_ranking(self) -> None:
        for agent in ("codex", "claude"):
            with self.subTest(agent=agent), mock.patch.object(recall, "run_source", return_value=hit(agent)) as run:
                self.invoke("--agent", agent, "--roles", "user", "--limit", "20")
                command = run.call_args.args[1]
                self.assertEqual(command[command.index("--roles") + 1], "user")

    def test_both_sources_remain_separate_and_ambiguous(self) -> None:
        with mock.patch.object(recall, "run_source", side_effect=lambda source, _: hit(source)):
            result = self.invoke("--agent", "codex", "--source", "all")
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual({c["source"] for c in result["candidates"]}, {"codex", "claude"})


if __name__ == "__main__":
    unittest.main()
