from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "session_history.py"
SPEC = importlib.util.spec_from_file_location("session_history", SCRIPT)
assert SPEC and SPEC.loader
history = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = history
SPEC.loader.exec_module(history)


def record(record_type: str, payload: dict, ordinal: int, timestamp: str) -> dict:
    return {"timestamp": timestamp, "ordinal": ordinal, "type": record_type, "payload": payload}


def message(item_id: str, role: str, text: str, ordinal: int, timestamp: str) -> dict:
    block_type = "input_text" if role == "user" else "output_text"
    return record(
        "response_item",
        {"id": item_id, "type": "message", "role": role, "content": [{"type": block_type, "text": text}]},
        ordinal,
        timestamp,
    )


class SessionHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "sessions"
        self.root.mkdir()
        self.cwd = str(Path(self.temp.name) / "project")
        Path(self.cwd).mkdir()
        self.session = "11111111-1111-1111-1111-111111111111"
        # Isolate from the invoking Codex session so results don't depend on
        # whether the suite runs inside Codex.
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CODEX_THREAD_ID", None)
        os.environ.pop("CODEX_SESSION_ID", None)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_rollout(self, name: str, rows: list[dict | str]) -> Path:
        path = self.root / "2026" / "09" / "09" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as handle:
            for row in rows:
                handle.write(row if isinstance(row, str) else json.dumps(row))
                handle.write("\n")
        return path

    def meta(self, *, session: str | None = None, cwd: str | None = None, source: str = "user") -> dict:
        return record(
            "session_meta",
            {
                "id": session or self.session,
                "cwd": cwd or self.cwd,
                "originator": "Codex Desktop",
                "thread_source": source,
                "git": {"branch": "main"},
            },
            0,
            "2026-09-09T01:00:00Z",
        )

    def test_extracts_conversation_and_drops_injected_developer_and_images(self) -> None:
        path = self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message("dev", "developer", "system instructions", 1, "2026-09-09T01:00:01Z"),
                message("injected", "user", "<environment_context>hidden</environment_context>", 2, "2026-09-09T01:00:02Z"),
                record(
                    "response_item",
                    {
                        "id": "mixed",
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_image", "image_url": "data:image/png;base64," + "A" * 1000},
                            {"type": "input_text", "text": "keep this exact preference"},
                        ],
                    },
                    3,
                    "2026-09-09T01:00:03Z",
                ),
                message("assistant", "assistant", "acknowledged preference", 4, "2026-09-09T01:00:04Z"),
            ],
        )
        turns, stats = history.extract_turns(path)
        self.assertEqual([turn.item_id for turn in turns], ["mixed", "assistant"])
        self.assertNotIn("base64", " ".join(turn.text for turn in turns))
        self.assertEqual(stats.messages_kept, 2)

    def test_auto_search_excludes_invoking_turn_and_finds_pre_compaction_context(self) -> None:
        first = self.write_rollout(
            f"rollout-a-{self.session}.jsonl",
            [
                self.meta(),
                message("old", "user", "We decided the retry ceiling is seven attempts because rate limits recover slowly.", 1, "2026-09-09T01:00:01Z"),
                message("old-answer", "assistant", "I will use seven attempts.", 2, "2026-09-09T01:00:02Z"),
                record("compacted", {"window_number": 2, "replacement_history": []}, 3, "2026-09-09T01:00:03Z"),
            ],
        )
        second = self.write_rollout(
            f"rollout-b-{self.session}.jsonl",
            [
                self.meta(),
                message("invoke", "user", "What did we decide about retry ceiling attempts?", 4, "2026-09-09T02:00:00Z"),
            ],
        )
        os.utime(first, (1, 1))
        os.utime(second, (2, 2))
        previous = os.environ.get("CODEX_THREAD_ID")
        os.environ["CODEX_THREAD_ID"] = self.session
        try:
            result = history.search_history(
                self.root,
                "retry ceiling attempts",
                cwd=self.cwd,
                scope="auto",
            )
        finally:
            if previous is None:
                os.environ.pop("CODEX_THREAD_ID", None)
            else:
                os.environ["CODEX_THREAD_ID"] = previous
        self.assertEqual(result["scope_used"], "current-task")
        self.assertEqual(result["excluded_latest_user_item"], "invoke")
        self.assertEqual(result["candidates"][0]["locator"]["item_id"], "old")

    def test_current_project_and_all_scopes(self) -> None:
        other_session = "22222222-2222-2222-2222-222222222222"
        other_cwd = str(Path(self.temp.name) / "other")
        Path(other_cwd).mkdir()
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("project", "user", "The cobalt deployment uses port 4317.", 1, "2026-09-01T01:00:00Z")],
        )
        self.write_rollout(
            f"rollout-{other_session}.jsonl",
            [self.meta(session=other_session, cwd=other_cwd), message("global", "user", "The zircon archive uses bucket glacier-nine.", 1, "2026-08-01T01:00:00Z")],
        )
        project = history.search_history(self.root, "cobalt deployment port", cwd=self.cwd, scope="current-project")
        global_result = history.search_history(self.root, "zircon archive bucket", cwd=self.cwd, scope="all")
        self.assertEqual(project["candidates"][0]["locator"]["item_id"], "project")
        self.assertEqual(global_result["candidates"][0]["locator"]["item_id"], "global")

    def test_cjk_retrieval_and_redaction(self) -> None:
        path = self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message("cjk", "user", "我们决定编译校验必须并行运行，令牌 sk-abcdefghijklmnop 必须隐藏。", 1, "2026-09-01T01:00:00Z"),
            ],
        )
        turns, stats = history.extract_turns(path)
        status, hits, _ = history.rank_turns(turns, "编译校验", 5)
        self.assertIn(status, ("confident", "ambiguous"))
        self.assertEqual(hits[0].item_id, "cjk")
        self.assertIn("[REDACTED:openai-key]", hits[0].text)
        self.assertNotIn("sk-abcdefghijklmnop", hits[0].text)
        self.assertEqual(stats.redactions, 1)

    def test_show_context_uses_item_anchor_across_files(self) -> None:
        self.write_rollout(
            f"rollout-a-{self.session}.jsonl",
            [self.meta(), message("before", "user", "first turn", 1, "2026-09-09T01:00:01Z")],
        )
        self.write_rollout(
            f"rollout-b-{self.session}.jsonl",
            [
                self.meta(),
                message("anchor", "assistant", "second turn", 2, "2026-09-09T01:00:02Z"),
                message("after", "user", "third turn", 3, "2026-09-09T01:00:03Z"),
            ],
        )
        result = history.show_context(self.root, self.session[:8], "anchor", before=1, after=1, max_chars=5000)
        self.assertEqual(result["status"], "ok")
        self.assertEqual([turn["locator"]["item_id"] for turn in result["turns"]], ["before", "anchor", "after"])
        self.assertTrue(result["turns"][1]["is_anchor"])

    def test_structural_subagent_session_is_excluded(self) -> None:
        parent = "33333333-3333-3333-3333-333333333333"
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(source="subagent"),
                self.meta(session=parent, source="user"),
                message("noise", "user", "private subagent planning", 2, "2026-09-09T01:00:02Z"),
            ],
        )
        result = history.search_history(self.root, "private subagent planning", cwd=self.cwd, scope="all")
        self.assertEqual(result["status"], "no_match")
        self.assertEqual(result["candidates"], [])

    def test_redacts_serialized_queries_and_quoted_assignments(self) -> None:
        path = self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message(
                    "secret",
                    "user",
                    'deployment PASSWORD="synthetic-secret" and bearer abcdefghijklmnop',
                    1,
                    "2026-09-09T01:00:01Z",
                ),
            ],
        )
        turns, _ = history.extract_turns(path)
        self.assertNotIn("synthetic-secret", turns[0].text)
        self.assertNotIn("abcdefghijklmnop", turns[0].text)
        result = history.search_history(
            self.root,
            "deployment sk-abcdefghijklmnop",
            cwd=self.cwd,
            scope="all",
        )
        serialized = json.dumps(result)
        self.assertNotIn("sk-abcdefghijklmnop", serialized)
        self.assertNotIn("query_terms", result)

    def test_show_always_includes_anchor_with_tight_budget(self) -> None:
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message("long-before", "user", "x" * 5000, 1, "2026-09-09T01:00:01Z"),
                message("must-show", "assistant", "anchor evidence", 2, "2026-09-09T01:00:02Z"),
            ],
        )
        result = history.show_context(self.root, self.session, "must-show", before=1, after=0, max_chars=1000)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(any(turn["is_anchor"] for turn in result["turns"]))
        self.assertIn("anchor evidence", next(turn["text"] for turn in result["turns"] if turn["is_anchor"]))

    def test_auto_escalates_past_ambiguous_current_task(self) -> None:
        old_session = "44444444-4444-4444-4444-444444444444"
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message("weak", "assistant", "The deployment theme was mentioned.", 1, "2026-09-09T01:00:01Z"),
                message("invoke", "user", "deployment theme host local mode", 2, "2026-09-09T01:00:02Z"),
            ],
        )
        self.write_rollout(
            f"rollout-{old_session}.jsonl",
            [
                self.meta(session=old_session),
                message("strong", "user", "We decided the deployment theme uses host local mode.", 1, "2026-08-09T01:00:01Z"),
            ],
        )
        result = history.search_history(
            self.root,
            "deployment theme host local mode",
            cwd=self.cwd,
            scope="auto",
            explicit_session_id=self.session,
        )
        self.assertEqual(result["scope_used"], "current-project")
        self.assertEqual(result["candidates"][0]["locator"]["item_id"], "strong")
        self.assertEqual([attempt["scope"] for attempt in result["scope_attempts"]], ["current-task", "current-project"])

    def test_annotation_keeps_user_comment_not_selected_assistant_text(self) -> None:
        annotation = (
            '# Response annotations:\n<response-annotations>\n'
            '[{"text":"assistant selection","annotation":"keep my actual correction"}]\n'
            '</response-annotations>\n\n## My request:\ncontinue with the lighter design'
        )
        path = self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("annotation", "user", annotation, 1, "2026-09-09T01:00:01Z")],
        )
        turns, _ = history.extract_turns(path)
        self.assertIn("keep my actual correction", turns[0].text)
        self.assertIn("continue with the lighter design", turns[0].text)
        self.assertNotIn("assistant selection", turns[0].text)

    def test_empty_query_and_hangul_are_distinct(self) -> None:
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("hangul", "user", "한국어 테스트 결정", 1, "2026-09-09T01:00:01Z")],
        )
        empty = history.search_history(self.root, "session history", cwd=self.cwd, scope="all")
        # A foreign session id keeps the recent-query heuristic from excluding
        # the only turn as the invoking one.
        hangul = history.search_history(
            self.root,
            "한국어 테스트",
            cwd=self.cwd,
            scope="all",
            explicit_session_id="22222222-2222-2222-2222-222222222222",
        )
        self.assertEqual(empty["status"], "empty_query")
        self.assertTrue(hangul["candidates"])

    def test_deeply_nested_malformed_record_is_skipped(self) -> None:
        nested = (
            '{"type":"response_item","payload":{"type":"message","junk":'
            + "[" * 10000
            + "0"
            + "]" * 10000
            + "}}"
        )
        path = self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), nested, message("after-bad", "user", "valid searchable statement", 2, "2026-09-09T01:00:02Z")],
        )
        turns, stats = history.extract_turns(path)
        self.assertEqual([turn.item_id for turn in turns], ["after-bad"])
        self.assertEqual(stats.malformed_records, 1)


if __name__ == "__main__":
    unittest.main()
