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
                self.assertIn("all", command)
                if agent == "claude":
                    self.assertEqual(command[command.index("--max-files") + 1], "0")
                self.assertEqual(result["candidates"][0]["source"], agent)
                self.assertTrue(result["confirmation"].startswith(f"recall [{agent}]:"))

    def test_other_source_is_explicit(self) -> None:
        with mock.patch.object(recall, "run_source", return_value=hit("claude")) as run:
            result = self.invoke("--agent", "codex", "--source", "other")
        self.assertEqual(run.call_args.args[0], "claude")
        self.assertEqual(result["candidates"][0]["source"], "claude")

    def test_both_sources_remain_separate_and_ambiguous(self) -> None:
        with mock.patch.object(recall, "run_source", side_effect=lambda source, _: hit(source)):
            result = self.invoke("--agent", "codex", "--source", "all")
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual({c["source"] for c in result["candidates"]}, {"codex", "claude"})


if __name__ == "__main__":
    unittest.main()
