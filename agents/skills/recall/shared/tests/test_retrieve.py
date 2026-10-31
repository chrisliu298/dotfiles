"""Behavioral cases for paraphrases, conversation context and retrieval boundaries."""
import importlib.util
import sys
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "retrieve.py"
SPEC = importlib.util.spec_from_file_location("retrieve", PATH)
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def row(session, text, order=1, role="user", date="2026-09-01"):
    return dict(session=session, text=text, order=order, role=role, date=date,
                line=order, confirmation=f"recall: {date} · {session} · {text[:30]}")


class RetrievalTests(unittest.TestCase):
    def test_variant_recovers_different_wording(self):
        rows = [row("a", "Set the retry budget to seven attempts.")]
        self.assertEqual(r.retrieve(rows, ["故障重试上限"])["status"], "no_match")
        found = r.retrieve(rows, ["故障重试上限", "retry budget"])
        self.assertEqual(found["candidates"][0]["session"], "a")
        self.assertEqual(found["candidates"][0]["matched_queries"], [2])
        self.assertTrue(found["verification_required"])

    def test_split_turn_evidence_keeps_roles_and_anchors(self):
        rows = [row("a", "Which transport should the orchard service use?"),
                row("a", "Use websocket.", 2, "assistant")]
        result = r.retrieve(rows, ["orchard websocket"])
        evidence = result["candidates"][0]["evidence"]
        self.assertEqual([e["line"] for e in evidence], [1, 2])
        self.assertEqual([e["role"] for e in evidence], ["user", "assistant"])
        self.assertEqual(result["status"], "ambiguous")

    def test_question_options_answer_window(self):
        rows = [row("a", "Choose orchard transport"),
                row("a", "There are several options.", 2, "assistant"),
                row("a", "websocket", 3)]
        hit = r.retrieve(rows, ["orchard websocket"])["candidates"][0]
        self.assertEqual([e["line"] for e in hit["evidence"]], [1, 2, 3])

    def test_never_stitch_different_sessions(self):
        rows = [row("a", "orchard"), row("b", "websocket")]
        self.assertEqual(r.retrieve(rows, ["orchard websocket"])["candidates"], [])

    def test_filters_precede_ranking_and_do_not_bridge_excluded_turn(self):
        rows = [row("a", "orchard"), row("a", "websocket", 2, "assistant")]
        self.assertEqual(r.retrieve(rows, ["orchard websocket"], roles="user")["candidates"], [])
        rows += [row("b", "orchard websocket", date="2026-09-20")]
        hit = r.retrieve(rows, ["orchard websocket"], limit=1, since="2026-09-10")["candidates"][0]
        self.assertEqual(hit["session"], "b")

    def test_sessions_are_diverse_even_with_many_duplicate_messages(self):
        rows = [row("a", "retry budget seven", i) for i in range(50)]
        rows += [row("b", "retry budget eight")]
        result = r.retrieve(rows, ["retry budget"], limit=2)
        self.assertEqual({c["session"] for c in result["candidates"]}, {"a", "b"})

    def test_session_fill_finds_description_spread_across_a_session(self):
        rows = [row("a", "Why is the orchard dashboard slow?"),
                row("a", "unrelated filler", 2, "assistant"), row("a", "more filler", 3),
                row("a", "unrelated filler again", 4, "assistant"),
                row("a", "The nightly websocket reconnect was the cause.", 5, "assistant"),
                row("b", "orchard pricing notes")]
        result = r.retrieve(rows, ["orchard dashboard slow nightly websocket reconnect"])
        self.assertEqual(result["candidates"][0]["session"], "a")
        self.assertEqual(result["candidates"][0]["match"], "session")
        self.assertEqual({e["line"] for e in result["candidates"][0]["evidence"]}, {1, 5})

    def test_session_fill_accepts_conversational_cjk_description(self):
        rows = [row("a", "看下多账号切换工具现在是自动还是手动"), row("a", "无关内容", 2, "assistant"),
                row("a", "无关", 3), row("a", "其他", 4, "assistant"),
                row("a", "已经打开自动切换", 5, "assistant"), row("b", "午饭吃什么")]
        result = r.retrieve(rows, ["之前问过多账号切换那个工具到底是自动换号还是要我手动换，后来让你直接打开了"])
        self.assertEqual([c["session"] for c in result["candidates"]], ["a"])

    def test_message_matches_rank_before_session_fill(self):
        rows = [row("a", "orchard dashboard"), row("a", "filler", 2), row("a", "filler", 3),
                row("a", "filler", 4), row("a", "nightly websocket", 5),
                row("c", "orchard dashboard nightly websocket")]
        candidates = r.retrieve(rows, ["orchard dashboard nightly websocket"])["candidates"]
        self.assertEqual([(c["session"], c["match"]) for c in candidates], [("c", "message"), ("a", "session")])

    def test_session_fill_counts_title_terms(self):
        rows = [dict(row("a", "it keeps timing out"), title="Orchard websocket outage"),
                dict(row("b", "lunch plans"), title="Weekend")]
        candidates = r.retrieve(rows, ["orchard websocket timing"])["candidates"]
        self.assertEqual([c["session"] for c in candidates], ["a"])

    def test_candidates_carry_title_and_opening(self):
        rows = [row("a", "Some setup question", 1),
                dict(row("a", "retry budget is seven", 2, "assistant"), title="Retry policy")]
        candidate = r.retrieve(rows, ["retry budget"])["candidates"][0]
        self.assertEqual(candidate["title"], "Retry policy")
        self.assertEqual(candidate["opening"], "Some setup question")

    def test_project_and_session_filters(self):
        rows = [dict(row("a1", "retry budget"), project="/Users/me/dotfiles"),
                dict(row("b2", "retry budget"), project="/Users/me/other-repo")]
        found = r.retrieve(rows, ["retry budget"], project="DOTFILES")["candidates"]
        self.assertEqual([c["session"] for c in found], ["a1"])
        found = r.retrieve(rows, ["retry budget"], session="b")
        self.assertEqual([c["session"] for c in found["candidates"]], ["b2"])
        self.assertEqual(found["coverage"]["session"], "b")

    def test_excerpt_is_centered_on_match(self):
        text = "preface " * 200 + "unique_marker is 42" + " tail" * 200
        self.assertIn("unique_marker", r.excerpt(text, ["unique_marker"]))
        self.assertLessEqual(len(r.excerpt(text, ["unique_marker"])), 602)


class TimelineTests(unittest.TestCase):
    def rows(self, *texts):
        return [dict(session="a", text=text, order=i, role="user", date="2026-09-01", line=i, epoch=1000.0 + i,
                     project="/work/app", title="T") for i, text in enumerate(texts)]

    def test_drops_system_and_harness_turns(self):
        rows = self.rows("Another Claude session sent a message: hi", "[Request interrupted by user]",
                         "Your response above was stopped", "(Re-invocation of /recall — x", "[Image: source: /a.png]",
                         "ship it")
        rows.append(dict(rows[0], text="scheduled tick", order=9, line=9, epoch=1009.0, system=True))
        found = r.list_window(rows, 0, 2000)
        self.assertEqual([m["text"] for m in found["sessions"][0]["messages"]], ["ship it"])
        self.assertEqual(found["coverage"]["messages_filtered"], 6)

    def test_keeps_real_requests_and_every_repeat(self):
        rows = self.rows("Generate a title for this report", "[Image: source: /a.png] 修复按钮", "继续", "只改文档", "继续")
        messages = r.list_window(rows, 0, 2000)["sessions"][0]["messages"]
        self.assertEqual([m["text"] for m in messages],
                         ["Generate a title for this report", "修复按钮", "继续", "只改文档", "继续"])
        self.assertEqual(messages[4]["line"], 4)

    def test_keeps_answers_to_questions(self):
        found = r.list_window(self.rows('Your questions have been answered: "x"="y"'), 0, 2000)
        self.assertEqual(found["coverage"]["messages_listed"], 1)

    def test_limit_and_clip_are_reported(self):
        found = r.list_window(self.rows("one " * 200, "two", "three"), 0, 2000, limit=2, max_chars=100)
        first = found["sessions"][0]["messages"][0]
        self.assertTrue(first["truncated"])
        self.assertEqual(first["chars"], 799)
        self.assertEqual(found["coverage"]["messages_omitted"], 1)

    def test_empty_window(self):
        self.assertEqual(r.list_window(self.rows("x"), 5000, 6000)["status"], "no_messages")


if __name__ == "__main__":
    unittest.main()
