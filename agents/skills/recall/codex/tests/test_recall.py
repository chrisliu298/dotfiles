from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "recall.py"
SPEC = importlib.util.spec_from_file_location("recall", SCRIPT)
assert SPEC and SPEC.loader
recall = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recall
SPEC.loader.exec_module(recall)


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


class RecallTests(unittest.TestCase):
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
        turns, stats = recall.extract_turns(path)
        self.assertEqual([turn.item_id for turn in turns], ["mixed", "assistant"])
        self.assertNotIn("base64", " ".join(turn.text for turn in turns))
        self.assertEqual(stats.messages_kept, 2)

    def test_current_task_scope_excludes_invoking_turn_and_finds_pre_compaction_context(self) -> None:
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
        os.environ["CODEX_THREAD_ID"] = self.session
        result = recall.search_history(self.root, "retry ceiling attempts", cwd=self.cwd, scope="current-task")
        self.assertEqual(result["scope_used"], "current-task")
        self.assertEqual(result["excluded_latest_user_item"], "invoke")
        self.assertIsNone(result["excluded_current_task"])
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
        project = recall.search_history(self.root, "cobalt deployment port", cwd=self.cwd, scope="current-project")
        global_result = recall.search_history(self.root, "zircon archive bucket", cwd=self.cwd, scope="all")
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
        turns, stats = recall.extract_turns(path)
        status, hits, _ = recall.rank_turns(turns, "编译校验", 5)
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
        result = recall.show_context(self.root, self.session[:8], "anchor", before=1, after=1, max_chars=5000)
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
        result = recall.search_history(self.root, "private subagent planning", cwd=self.cwd, scope="all")
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
        turns, _ = recall.extract_turns(path)
        self.assertNotIn("synthetic-secret", turns[0].text)
        self.assertNotIn("abcdefghijklmnop", turns[0].text)
        result = recall.search_history(
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
        result = recall.show_context(self.root, self.session, "must-show", before=1, after=0, max_chars=1000)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(any(turn["is_anchor"] for turn in result["turns"]))
        self.assertIn("anchor evidence", next(turn["text"] for turn in result["turns"] if turn["is_anchor"]))

    def test_auto_excludes_current_task_by_default(self) -> None:
        old_session = "44444444-4444-4444-4444-444444444444"
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message("live", "user", "We decided the deployment theme uses host local mode today.", 1, "2026-09-09T01:00:01Z"),
                message("invoke", "user", "remind me of the deployment theme", 2, "2026-09-09T01:00:02Z"),
            ],
        )
        self.write_rollout(
            f"rollout-{old_session}.jsonl",
            [
                self.meta(session=old_session),
                message("past", "user", "We decided the deployment theme uses host local mode.", 1, "2026-08-09T01:00:01Z"),
            ],
        )
        result = recall.search_history(
            self.root,
            "deployment theme host local mode",
            cwd=self.cwd,
            scope="auto",
            explicit_session_id=self.session,
        )
        self.assertEqual(result["scope_used"], "current-project")
        self.assertEqual(result["excluded_current_task"], self.session)
        self.assertEqual([hit["locator"]["item_id"] for hit in result["candidates"]], ["past"])
        self.assertEqual([attempt["scope"] for attempt in result["scope_attempts"]], ["current-project"])

    def test_auto_escalates_from_project_to_all(self) -> None:
        other_session = "55555555-5555-5555-5555-555555555555"
        other_cwd = str(Path(self.temp.name) / "other")
        Path(other_cwd).mkdir()
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("near", "user", "Unrelated cobalt note for this project.", 1, "2026-09-01T01:00:00Z")],
        )
        self.write_rollout(
            f"rollout-{other_session}.jsonl",
            [self.meta(session=other_session, cwd=other_cwd), message("far", "user", "We decided the zircon archive uses bucket glacier-nine.", 1, "2026-08-01T01:00:00Z")],
        )
        result = recall.search_history(
            self.root,
            "zircon archive bucket",
            cwd=self.cwd,
            scope="auto",
            explicit_session_id="99999999-9999-9999-9999-999999999999",
        )
        self.assertEqual(result["status"], "confident")
        self.assertEqual(result["scope_used"], "all")
        self.assertEqual([attempt["scope"] for attempt in result["scope_attempts"]], ["current-project", "all"])
        self.assertEqual(result["candidates"][0]["locator"]["item_id"], "far")
        self.assertEqual(result["candidates"][0]["kind"], "statement")

    def test_invoking_task_is_excluded_without_session_env(self) -> None:
        old_session = "66666666-6666-6666-6666-666666666666"
        self.write_rollout(
            f"rollout-{old_session}.jsonl",
            [self.meta(session=old_session), message("past", "user", "We decided the ferrite cache holds 512 entries.", 1, "2026-08-01T01:00:00Z")],
        )
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message("earlier", "assistant", "The ferrite cache size is still open.", 1, "2026-09-09T01:00:00Z"),
                message("invoke", "user", "what did we say about ferrite cache entries?", 2, "2026-09-09T01:00:01Z"),
            ],
        )
        result = recall.search_history(self.root, "ferrite cache entries", cwd=self.cwd, scope="all")
        self.assertEqual(result["invoking_turn_resolution"], "recent-query-match")
        self.assertEqual(result["current_task_exclusion"], "inferred")
        self.assertEqual(result["excluded_current_task"], self.session)
        self.assertEqual([hit["locator"]["item_id"] for hit in result["candidates"]], ["past"])

    def test_confirmation_line_format(self) -> None:
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message("user-turn", "user", "We decided the  quartz\nlimit is 42.", 1, "2026-09-09T12:00:00Z"),
                message("agent-turn", "assistant", "Proposed quartz limit 42 for now.", 2, "2026-09-09T12:00:01Z"),
            ],
        )
        result = recall.search_history(
            self.root,
            "quartz limit",
            cwd=self.cwd,
            scope="all",
            explicit_session_id="99999999-9999-9999-9999-999999999999",
        )
        lines = {hit["locator"]["item_id"]: hit["confirmation"] for hit in result["candidates"]}
        self.assertRegex(lines["user-turn"], r"^recall: \d{4}-\d{2}-\d{2} · 11111111 · We decided the quartz limit is 42\.$")
        self.assertRegex(lines["agent-turn"], r"^recall: \d{4}-\d{2}-\d{2} · 11111111 · agent turn, unconfirmed by user: ")
        self.assertEqual(result["confirmation"], result["candidates"][0]["confirmation"])
        self.assertNotIn("\n", result["confirmation"])

    def test_cli_emits_json_for_explicit_root(self) -> None:
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("cli", "user", "The obsidian vault syncs nightly.", 1, "2026-09-09T01:00:01Z")],
        )
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = recall.main(["--root", str(self.root), "search", "--scope", "all", "-q", "obsidian vault nightly"])
        self.assertEqual(code, 0)
        output = json.loads(buffer.getvalue())
        self.assertEqual(output["candidates"][0]["locator"]["item_id"], "cli")

    def test_unterminated_private_key_body_is_redacted(self) -> None:
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAKj34GkxFhD90vcN\nLYLInFxkOWyHd8q2mrc3oPDVLCSb\n"
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message("closed", "user", "old key -----BEGIN PRIVATE KEY-----\nAAAAbody\n-----END PRIVATE KEY----- kept tail", 1, "2026-09-09T01:00:01Z"),
                message("open", "user", "pasted key:\n" + pem, 2, "2026-09-09T01:00:02Z"),
            ],
        )
        result = recall.show_context(self.root, self.session, "closed", before=0, after=1, max_chars=5000)
        texts = {turn["locator"]["item_id"]: turn["text"] for turn in result["turns"]}
        self.assertIn("kept tail", texts["closed"])
        self.assertNotIn("AAAAbody", texts["closed"])
        self.assertIn("[REDACTED:private-key]", texts["open"])
        self.assertNotIn("MIIBOgIBAAJBAKj34", texts["open"])
        self.assertNotIn("LYLInFxkOWyHd8q2", texts["open"])

    def test_question_top_hit_is_not_confident(self) -> None:
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("ask", "user", "Should the zircon archive use bucket glacier-nine?", 1, "2026-09-09T01:00:01Z")],
        )
        result = recall.search_history(
            self.root,
            "zircon archive bucket",
            cwd=self.cwd,
            scope="all",
            explicit_session_id="99999999-9999-9999-9999-999999999999",
        )
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["candidates"][0]["kind"], "question")

    def test_question_with_decision_cue_is_question(self) -> None:
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [
                self.meta(),
                message("ask", "user", "Should we choose bucket glacier-nine for the zircon archive?", 1, "2026-09-09T01:00:01Z"),
                message("mixed", "user", "We decided on glacier-nine. Does the zircon archive need more?", 2, "2026-09-09T01:00:02Z"),
            ],
        )
        turns, _ = recall.extract_turns(next(self.root.rglob("*.jsonl")))
        kinds = {turn.item_id: recall.turn_kind(turn) for turn in turns}
        self.assertEqual(kinds, {"ask": "question", "mixed": "statement"})
        result = recall.search_history(
            self.root,
            "choose zircon archive bucket",
            cwd=self.cwd,
            scope="all",
            explicit_session_id="99999999-9999-9999-9999-999999999999",
        )
        self.assertEqual(result["candidates"][0]["locator"]["item_id"], "ask")
        self.assertNotEqual(result["status"], "confident")

    def test_auto_does_not_escalate_past_ambiguous_project(self) -> None:
        other_session = "77777777-7777-7777-7777-777777777777"
        other_cwd = str(Path(self.temp.name) / "other")
        Path(other_cwd).mkdir()
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("near", "assistant", "The zircon archive bucket is still undecided here.", 1, "2026-09-01T01:00:00Z")],
        )
        self.write_rollout(
            f"rollout-{other_session}.jsonl",
            [self.meta(session=other_session, cwd=other_cwd), message("far", "user", "We decided the zircon archive uses bucket glacier-nine.", 1, "2026-08-01T01:00:00Z")],
        )
        result = recall.search_history(
            self.root,
            "zircon archive bucket",
            cwd=self.cwd,
            scope="auto",
            explicit_session_id="99999999-9999-9999-9999-999999999999",
        )
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["scope_used"], "current-project")
        self.assertEqual([attempt["scope"] for attempt in result["scope_attempts"]], ["current-project"])
        self.assertEqual(result["candidates"][0]["locator"]["item_id"], "near")

    def test_escalation_parses_each_transcript_once(self) -> None:
        other_session = "88888888-8888-8888-8888-888888888888"
        other_cwd = str(Path(self.temp.name) / "other")
        Path(other_cwd).mkdir()
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("near", "user", "Unrelated cobalt note for this project.", 1, "2026-09-01T01:00:00Z")],
        )
        self.write_rollout(
            f"rollout-{other_session}.jsonl",
            [self.meta(session=other_session, cwd=other_cwd), message("far", "user", "We decided the zircon archive uses bucket glacier-nine.", 1, "2026-08-01T01:00:00Z")],
        )
        with mock.patch.object(recall, "extract_turns", wraps=recall.extract_turns) as extract, mock.patch.object(
            recall, "tokenize", wraps=recall.tokenize
        ) as tokenize:
            result = recall.search_history(
                self.root,
                "zircon archive bucket",
                cwd=self.cwd,
                scope="auto",
                explicit_session_id="99999999-9999-9999-9999-999999999999",
            )
        self.assertEqual(result["scope_used"], "all")
        parsed = [call.args[0].name for call in extract.call_args_list]
        self.assertEqual(sorted(parsed), sorted(set(parsed)))
        tokenized = [call.args[0] for call in tokenize.call_args_list]
        self.assertEqual(tokenized.count("Unrelated cobalt note for this project."), 1)

    def test_old_query_match_is_not_inferred_as_current_task(self) -> None:
        path = self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("old", "user", "what did we say about ferrite cache entries?", 1, "2026-08-01T01:00:00Z")],
        )
        os.utime(path, (1_000_000, 1_000_000))
        result = recall.search_history(self.root, "ferrite cache entries", cwd=self.cwd, scope="all")
        self.assertEqual(result["current_task_exclusion"], "unresolved")
        self.assertEqual([hit["locator"]["item_id"] for hit in result["candidates"]], ["old"])
        turns, _ = recall.extract_turns(path)
        kept, session, _, _ = recall.exclude_current_task(
            turns, "", "ferrite cache entries", whole_session=True, now=1_000_000 + 60
        )
        self.assertEqual((len(kept), session), (0, self.session))

    def test_current_task_exclusion_state_is_reported(self) -> None:
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("fact", "user", "We decided the basalt queue drains hourly.", 1, "2026-09-09T01:00:01Z")],
        )
        unresolved = recall.search_history(self.root, "basalt drains", cwd=self.cwd, scope="all")
        resolved = recall.search_history(
            self.root,
            "basalt queue",
            cwd=self.cwd,
            scope="all",
            explicit_session_id="99999999-9999-9999-9999-999999999999",
        )
        self.assertEqual(unresolved["current_task_exclusion"], "unresolved")
        self.assertEqual(resolved["current_task_exclusion"], "resolved")

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
        turns, _ = recall.extract_turns(path)
        self.assertIn("keep my actual correction", turns[0].text)
        self.assertIn("continue with the lighter design", turns[0].text)
        self.assertNotIn("assistant selection", turns[0].text)

    def test_referenced_chats_wrapper_keeps_actual_user_request(self) -> None:
        wrapped = (
            '\n## Referenced chats with Codex:\n'
            'These are live references to Codex tasks, not task contents.\n'
            '[{"hostId":"local","threadId":"older-task"}]\n'
            '## My request:\n'
            'Which reasoning effort should CLF Training and CoT use with GPT-6 Sol?'
        )
        path = self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("wrapped", "user", wrapped, 1, "2026-09-09T01:00:01Z")],
        )
        turns, _ = recall.extract_turns(path)
        self.assertEqual(len(turns), 1)
        self.assertEqual(
            turns[0].text,
            "Which reasoning effort should CLF Training and CoT use with GPT-6 Sol?",
        )

    def test_empty_query_and_hangul_are_distinct(self) -> None:
        self.write_rollout(
            f"rollout-{self.session}.jsonl",
            [self.meta(), message("hangul", "user", "한국어 테스트 결정", 1, "2026-09-09T01:00:01Z")],
        )
        empty = recall.search_history(self.root, "session history", cwd=self.cwd, scope="all")
        # A foreign session id keeps the recent-query heuristic from excluding
        # the only turn as the invoking one.
        hangul = recall.search_history(
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
        turns, stats = recall.extract_turns(path)
        self.assertEqual([turn.item_id for turn in turns], ["after-bad"])
        self.assertEqual(stats.malformed_records, 1)


if __name__ == "__main__":
    unittest.main()
