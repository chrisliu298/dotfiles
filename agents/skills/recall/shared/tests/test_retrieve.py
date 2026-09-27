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

    def test_excerpt_is_centered_on_match(self):
        text = "preface " * 200 + "unique_marker is 42" + " tail" * 200
        self.assertIn("unique_marker", r.excerpt(text, ["unique_marker"]))
        self.assertLessEqual(len(r.excerpt(text, ["unique_marker"])), 602)


if __name__ == "__main__":
    unittest.main()
