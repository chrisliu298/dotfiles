import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "agent-ask"
USER = "ou_user"
SID = "sid-r2v"
QUESTIONS = [{"question": "先上哪个存点？", "header": "选存点", "multiSelect": False,
              "options": [{"label": "s550", "description": "已复核"}, {"label": "s650", "description": ""}]},
             {"question": "通知谁？", "header": "通知", "multiSelect": True,
              "options": [{"label": "Compare"}, {"label": "Rating"}]}]

FAKE_LARK = """#!/usr/bin/env python3
import json, os, sys
calls = os.environ["FAKE_LARK_LOG"]
n = sum(1 for _ in open(calls)) if os.path.exists(calls) else 0
with open(calls, "a") as f:
    f.write(json.dumps({"args": sys.argv[1:], "stdin": sys.stdin.read() if "-" in sys.argv else ""}) + "\\n")
print(json.dumps({"ok": True, "data": {"message_id": f"om_{n}"}}))
"""


@pytest.fixture
def ctx(tmp_path):
    lark = tmp_path / "lark"
    lark.write_text(FAKE_LARK)
    lark.chmod(0o755)
    root = tmp_path / "state/agent-ask"
    root.mkdir(parents=True)
    (root / "config.json").write_text(json.dumps({"profile": "p", "chat_id": "oc_me", "user_open_id": USER}))
    sessions = tmp_path / ".claude/sessions"
    sessions.mkdir(parents=True)
    (sessions / "1.json").write_text(json.dumps({"sessionId": SID, "name": "Eval (R2V)"}))
    (sessions / "2.json").write_text(json.dumps({"sessionId": "sid-other", "name": "dotfiles"}))
    env = {k: os.environ[k] for k in ("PATH", "LANG") if k in os.environ}
    env.update(HOME=str(tmp_path), XDG_STATE_HOME=str(tmp_path / "state"), AGENT_ASK_LARK=str(lark),
               FAKE_LARK_LOG=str(tmp_path / "calls.jsonl"), TMUX="/tmp/tmux,1,0", AGENT_ASK_WAIT_SLICE="0.05",
               AGENT_ASK_WAIT_LIMIT="5")
    return tmp_path, root, env


def run(ctx, *args, event=None, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=json.dumps(event) if event is not None else "",
                          capture_output=True, text=True, env=env or ctx[2])


def ask(ctx, sid=SID, tool_use_id="toolu_1", env=None):
    event = {"session_id": sid, "tool_use_id": tool_use_id, "cwd": "/x/seedance-verifier-clf",
             "tool_name": "AskUserQuestion", "tool_input": {"questions": QUESTIONS}}
    return event, run(ctx, "hook-ask", event=event, env=env)


def calls(ctx):
    path = ctx[0] / "calls.jsonl"
    return [json.loads(line) for line in open(path)] if path.exists() else []


def record(ctx):
    [path] = (ctx[1] / "questions").glob("*.json")
    return json.loads(path.read_text())


def click(ctx, qid, i, pick, operator=USER, form=None):
    """Drive the hub's click handler the way one callback would; returns the card it answers with."""
    code = (f"import importlib.machinery,json,sys; m=importlib.machinery.SourceFileLoader('a',{str(SCRIPT)!r}).load_module();"
            f"a=json.loads(sys.stdin.read()); print(json.dumps(m.on_action(*a), ensure_ascii=False))")
    args = [operator, {"qid": qid, "i": i, "pick": pick}, form]
    out = subprocess.run([sys.executable, "-c", code], input=json.dumps(args), capture_output=True, text=True,
                         env=ctx[2])
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_in_scope_question_goes_to_feishu_and_terminal_dialog_is_denied(ctx):
    _, result = ask(ctx)
    out = json.loads(result.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    rec = record(ctx)
    assert rec["status"] == "pending" and rec["session"] == "Eval (R2V)" and rec["message_id"] == "om_0"
    card = json.loads(calls(ctx)[0]["stdin"])
    assert "Eval (R2V)" in card["header"]["title"]["content"]
    assert rec["qid"] in out["permissionDecisionReason"]
    assert len(calls(ctx)) == 1  # a lone question needs no summary


def test_out_of_scope_sessions_fall_through(ctx):
    _, result = ask(ctx, sid="sid-other")
    assert result.stdout == ""  # the terminal dialog goes ahead
    assert not list((ctx[1] / "questions").glob("*.json"))
    env = dict(ctx[2])
    env.pop("TMUX")
    ask(ctx, env=env)
    assert not list((ctx[1] / "questions").glob("*.json"))


def test_only_the_user_can_answer_and_all_questions_must_be_answered(ctx):
    ask(ctx)
    qid = record(ctx)["qid"]
    click(ctx, qid, 0, "s650", operator="ou_someone_else")
    assert record(ctx)["answers"] == {}
    click(ctx, qid, 0, "s650")
    assert record(ctx)["status"] == "pending"  # second question still open
    click(ctx, qid, 0, "s550")
    assert record(ctx)["answers"]["0"] == "s650"  # first answer sticks
    click(ctx, qid, 1, "__form__", form={"c0": True, "c1": True, "t1": "都要"})
    rec = record(ctx)
    assert rec["status"] == "answered" and rec["answers"]["1"] == "Compare, Rating（补充：都要）"


def test_free_text_answer_and_empty_submit_is_ignored(ctx):
    ask(ctx)
    qid = record(ctx)["qid"]
    click(ctx, qid, 0, "__form__", form={"t0": "  "})
    assert record(ctx)["answers"] == {}
    click(ctx, qid, 0, "__form__", form={"t0": "先等 Eval 出数"})
    assert record(ctx)["answers"]["0"] == "先等 Eval 出数"


def test_waiter_wakes_the_session_with_the_answer_once(ctx):
    event, _ = ask(ctx)
    qid = record(ctx)["qid"]
    click(ctx, qid, 0, "s550")
    click(ctx, qid, 1, "__form__", form={"c0": False, "c1": True})
    woke = run(ctx, "hook-wait", event=event)
    assert woke.returncode == 2 and "s550" in woke.stderr and "Rating" in woke.stderr
    rec = record(ctx)
    assert rec["status"] == "delivered"
    assert any("已送达" in arg for arg in calls(ctx)[-1]["args"])  # card stamped by the receiving side
    again = run(ctx, "hook-deliver", event={"session_id": SID, "hook_event_name": "PostToolUse"})
    assert again.stdout == ""


def test_busy_session_gets_the_answer_at_its_next_tool_call(ctx):
    ask(ctx)
    qid = record(ctx)["qid"]
    click(ctx, qid, 0, "s550")
    click(ctx, qid, 1, "__form__", form={"c0": True, "c1": False})
    other = run(ctx, "hook-deliver", event={"session_id": "sid-other", "hook_event_name": "PostToolUse"})
    assert other.stdout == ""
    got = json.loads(run(ctx, "hook-deliver", event={"session_id": SID, "hook_event_name": "PostToolUse"}).stdout)
    assert "s550" in got["hookSpecificOutput"]["additionalContext"]
    assert record(ctx)["status"] == "delivered"


def test_withdraw_greys_the_card_and_releases_the_waiter(ctx):
    event, _ = ask(ctx)
    qid = record(ctx)["qid"]
    assert run(ctx, "withdraw", qid, "已按", "s550", "推进").returncode == 0
    assert record(ctx)["status"] == "withdrawn"
    assert run(ctx, "hook-wait", event=event).returncode == 0
    click(ctx, qid, 0, "s650")
    assert record(ctx)["answers"] == {}


def test_long_questions_are_sent_back_to_be_shortened(ctx):
    long = [{"question": "背" * 121, "header": "x", "multiSelect": False,
             "options": [{"label": "甲", "description": "说" * 81}, {"label": "乙"}]}]
    event = {"session_id": SID, "tool_use_id": "toolu_long", "cwd": "/x", "tool_input": {"questions": long}}
    result = run(ctx, "hook-ask", event=event)
    reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "没有发出" in reason and "121 字" in reason and "81 字" in reason
    assert calls(ctx) == [] and not list((ctx[1] / "questions").glob("*.json"))


def test_unclear_closes_the_card_and_asks_for_a_rewrite(ctx):
    event, _ = ask(ctx)
    qid = record(ctx)["qid"]
    card = click(ctx, qid, -1, "__unclear__", form={"t1": "s550 是什么"})
    rec = record(ctx)
    assert rec["status"] == "answered" and rec["unclear"] == "s550 是什么"
    assert "没看懂" in card["header"]["title"]["content"]  # the click redraws the card as unclear
    woke = run(ctx, "hook-wait", event=event)
    assert woke.returncode == 2 and "没看懂" in woke.stderr and "s550 是什么" in woke.stderr
    assert "重新调用 AskUserQuestion" in woke.stderr
    click(ctx, qid, 0, "s550")
    assert record(ctx)["answers"] == {}  # a closed card takes no more clicks


def test_newest_open_card_lists_the_others_and_no_message_is_deleted(ctx):
    ask(ctx, tool_use_id="toolu_a")
    ask(ctx, tool_use_id="toolu_b")
    newest = calls(ctx)[-1]
    args = newest["args"]
    assert args[3:5] == ["messages", "patch"] and args[args.index("--message-id") + 1] == "om_1"
    assert "还有 1 条没答" in args[args.index("--data") + 1]
    assert not any("delete" in c["args"] for c in calls(ctx))


def card_of(ctx, n=0):
    return json.loads(calls(ctx)[n]["stdin"])


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def test_every_question_form_renders_its_own_controls(ctx):
    ask(ctx)
    nodes = list(walk(card_of(ctx)))
    buttons = [n["text"]["content"] for n in nodes if n.get("tag") == "button"]
    # single choice: one button per option; multi choice: checkboxes, not buttons
    assert {"s550", "s650", "提交文字", "提交所选", "🤔 没看懂"} <= set(buttons)
    assert "Compare" not in buttons
    assert [n["text"]["content"] for n in nodes if n.get("tag") == "checker"] == ["Compare", "Rating"]
    assert buttons.count("🤔 没看懂") == 1  # only on the last question
    assert all(n["tag"] == "form" for n in nodes if n.get("name", "").startswith("f"))


def test_single_choice_click_carries_the_text_box_as_a_note(ctx):
    ask(ctx)
    qid = record(ctx)["qid"]
    click(ctx, qid, 0, "s550", form={"t0": "先只给 Compare"})
    assert record(ctx)["answers"]["0"] == "s550（补充：先只给 Compare）"
    click(ctx, qid, 1, "__form__", form={"c0": False, "c1": False})
    assert "1" not in record(ctx)["answers"]  # nothing ticked, nothing typed
    click(ctx, qid, 1, "__form__", form={"c0": False, "c1": False, "t1": "都不用"})
    assert record(ctx)["answers"]["1"] == "都不用"


def test_option_preview_is_shown_folded(ctx):
    q = [{"question": "用哪版表头？", "header": "表头", "multiSelect": False,
          "options": [{"label": "甲", "preview": "| a | b |"}, {"label": "乙"}]}]
    run(ctx, "hook-ask", event={"session_id": SID, "tool_use_id": "toolu_p", "cwd": "/x", "tool_input": {"questions": q}})
    panels = [n for n in walk(card_of(ctx)) if n.get("tag") == "collapsible_panel"]
    assert len(panels) == 1 and "| a | b |" in json.dumps(panels[0], ensure_ascii=False)


def test_click_answers_with_the_redrawn_card_and_patches_nothing(ctx):
    ask(ctx)
    qid = record(ctx)["qid"]
    sent = len(calls(ctx))
    partial = click(ctx, qid, 0, "s550")
    assert "s550" in json.dumps(partial, ensure_ascii=False) and "已答" not in partial["header"]["title"]["content"]
    done = click(ctx, qid, 1, "__form__", form={"c0": True})
    assert "已答" in done["header"]["title"]["content"]
    assert len(calls(ctx)) == sent  # no message API call stands between the click and the redraw
    assert click(ctx, qid, 0, "s650") is None  # a closed card is left alone
