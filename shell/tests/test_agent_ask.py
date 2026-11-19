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
print(json.dumps({"ok": True, "data": {"message_id": f"om_{n}", "chat_id": f"oc_{n}"}}))
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
    long = [{"question": "背" * 161, "header": "x", "multiSelect": False,
             "options": [{"label": "甲", "description": "说" * 101}, {"label": "乙"}]}]
    event = {"session_id": SID, "tool_use_id": "toolu_long", "cwd": "/x", "tool_input": {"questions": long}}
    result = run(ctx, "hook-ask", event=event)
    reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "没有发出" in reason and "161 字" in reason and "101 字" in reason
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
    # single choice: one 选这个 button beside each option; multi choice: checkboxes, not buttons
    assert buttons.count("选这个") == 2 and {"提交文字", "提交所选", "🤔 没看懂"} <= set(buttons)
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


def deliver_hooks():
    """The hook-deliver commands exactly as agents/claude/settings.json registers them."""
    settings = json.loads((SCRIPT.parents[1] / "agents/claude/settings.json").read_text())
    return [hook["command"] for event in ("UserPromptSubmit", "PostToolUse") for group in settings["hooks"][event]
            for hook in group["hooks"] if "hook-deliver" in hook["command"]]


def run_hook(ctx, command, event):
    # Only the python3 under bin/ can run agent-ask: a hook that starts Python needlessly is visible.
    bin_dir = ctx[0] / "bin"
    bin_dir.mkdir(exist_ok=True)
    if not (bin_dir / "python3").exists():
        (bin_dir / "python3").symlink_to(sys.executable)
    empty = ctx[0] / "empty"
    empty.mkdir(exist_ok=True)
    env = {**ctx[2], "PATH": str(empty)}
    command = command.replace("~/.local/bin/agent-ask", str(SCRIPT))
    started = command.replace("python3", str(bin_dir / "python3"))
    return (subprocess.run(["/bin/sh", "-c", command], input=json.dumps(event), capture_output=True, text=True, env=env),
            subprocess.run(["/bin/sh", "-c", started], input=json.dumps(event), capture_output=True, text=True, env=env))


def test_per_tool_hook_starts_python_only_while_an_answer_awaits_delivery(ctx):
    commands = deliver_hooks()
    assert len(commands) == 2
    event = {"session_id": SID, "hook_event_name": "PostToolUse"}
    ask(ctx)
    for command in commands:
        idle, _ = run_hook(ctx, command, event)
        assert (idle.returncode, idle.stdout, idle.stderr) == (0, "", "")
    qid = record(ctx)["qid"]
    click(ctx, qid, 0, "s550")
    click(ctx, qid, 1, "__form__", form={"c0": True, "c1": False})
    without_python, delivered = run_hook(ctx, commands[1], event)
    assert without_python.returncode != 0  # it did try to start Python
    assert "s550" in json.loads(delivered.stdout)["hookSpecificOutput"]["additionalContext"]
    assert record(ctx)["status"] == "delivered"
    for command in commands:
        after, _ = run_hook(ctx, command, event)
        assert (after.returncode, after.stdout) == (0, "")


# ---- thread replies -------------------------------------------------------------------

def message(ctx, mid, root, text="等他的排上之后，我们再改回来", sender=USER, chat="oc_me"):
    """Drive the hub's message handler the way one im.message.receive_v1 event would."""
    code = (f"import importlib.machinery,json,sys; m=importlib.machinery.SourceFileLoader('a',{str(SCRIPT)!r}).load_module();"
            f"a=json.loads(sys.stdin.read()); print(m.on_message(*a))")
    msg = {"message_id": mid, "root_id": root, "parent_id": root, "chat_id": chat, "message_type": "text",
           "content": json.dumps({"text": text}, ensure_ascii=False)}
    out = subprocess.run([sys.executable, "-c", code], input=json.dumps([sender, msg]), capture_output=True, text=True,
                         env=ctx[2])
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def answered(ctx):
    ask(ctx)
    qid = record(ctx)["qid"]
    click(ctx, qid, 0, "s550")
    click(ctx, qid, 1, "__form__", form={"c0": True})
    run(ctx, "hook-deliver", event={"session_id": SID, "hook_event_name": "PostToolUse"})
    return record(ctx)


def test_reply_under_an_answered_card_reaches_the_session_once(ctx):
    card = answered(ctx)["message_id"]
    assert "for Eval (R2V)" in message(ctx, "om_u1", card)
    assert "already filed" in message(ctx, "om_u1", card)  # Feishu redelivered the same event
    other = run(ctx, "hook-deliver", event={"session_id": "sid-other", "hook_event_name": "PostToolUse"})
    assert other.stdout == ""
    got = json.loads(run(ctx, "hook-deliver", event={"session_id": SID, "hook_event_name": "PostToolUse"}).stdout)
    text = got["hookSpecificOutput"]["additionalContext"]
    assert "用户本人" in text and "等他的排上之后" in text and text.count("等他的排上之后") == 1
    assert any(c["args"][:3] == ["--profile", "p", "im"] and "reactions" in c["args"] for c in calls(ctx))
    again = run(ctx, "hook-deliver", event={"session_id": SID, "hook_event_name": "PostToolUse"})
    assert again.stdout == ""


def test_only_the_users_messages_in_threads_we_started_are_taken(ctx):
    card = answered(ctx)["message_id"]
    assert "ignored" in message(ctx, "om_x1", card, sender="ou_someone_else")
    assert "ignored" in message(ctx, "om_x2", card, chat="oc_group")
    assert "names no session" in message(ctx, "om_x3", "om_unrelated")  # answered by the hub, not filed
    assert not list((ctx[1] / "inbox").glob("*.json")) if (ctx[1] / "inbox").exists() else True


def test_idle_session_is_woken_and_its_reply_goes_back_into_the_thread(ctx, tmp_path):
    card = answered(ctx)["message_id"]
    message(ctx, "om_u2", card)
    listen = run(ctx, "hook-listen", event={"session_id": SID})
    assert listen.returncode == 2 and "等他的排上之后" in listen.stderr
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"type": "assistant", "timestamp": "2999-01-01T00:00:00Z",
                                      "message": {"content": [{"type": "text", "text": "好，排上后改回"}]}}) + "\n")
    run(ctx, "hook-reply", event={"session_id": SID, "transcript_path": str(transcript)})
    posts = [c for c in calls(ctx) if "+messages-reply" in c["args"]]
    assert posts and posts[-1]["args"][posts[-1]["args"].index("--message-id") + 1] == "om_u2"
    assert "好，排上后改回" in posts[-1]["stdin"]
    n = len(posts)
    run(ctx, "hook-reply", event={"session_id": SID, "transcript_path": str(transcript)})
    assert len([c for c in calls(ctx) if "+messages-reply" in c["args"]]) == n  # posted once


def test_reply_under_a_notification_goes_to_the_session_that_sent_it(ctx):
    env = {**ctx[2], "TMUX": "/tmp/tmux,1,0"}
    code = (f"import importlib.machinery; m=importlib.machinery.SourceFileLoader('a',{str(SCRIPT)!r}).load_module();"
            "m.owning_session=lambda: {'sessionId': 'sid-r2v', 'name': 'Eval (R2V)'}; m.notify('存点评完了')")
    assert subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True).returncode == 0
    sent = [c for c in calls(ctx) if "+messages-send" in c["args"]][-1]
    mid = f"om_{calls(ctx).index(sent)}"
    assert "for Eval (R2V)" in message(ctx, "om_u3", mid, text="分数多少？")
    got = json.loads(run(ctx, "hook-deliver", event={"session_id": SID, "hook_event_name": "PostToolUse"}).stdout)
    assert "推送" in got["hookSpecificOutput"]["additionalContext"]


def test_listener_of_the_latest_stop_waits_and_earlier_ones_leave(ctx):
    assert run(ctx, "hook-listen", event={"session_id": "sid-other"}).returncode == 0
    import time

    def listen():
        p = subprocess.Popen([sys.executable, str(SCRIPT), "hook-listen"], stdin=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=ctx[2], text=True)
        p.stdin.write(json.dumps({"session_id": SID}))
        p.stdin.close()
        return p

    card = answered(ctx)["message_id"]
    first = listen()
    time.sleep(0.5)
    second = listen()
    assert first.wait(timeout=5) == 0  # replaced, left without taking anything
    message(ctx, "om_u9", card)
    assert second.wait(timeout=10) == 2 and "等他的排上之后" in second.stderr.read()


# ---- talking to a session by name or in its group ---------------------------------------

def top(ctx, mid, text, chat="oc_me", sender=USER):
    return message(ctx, mid, None, text=text, sender=sender, chat=chat)


def with_sessions(ctx, *names):
    for i, name in enumerate(names):
        (ctx[0] / f".claude/sessions/{os.getpid() if i == 0 else os.getppid()}.json").write_text(
            json.dumps({"sessionId": f"sid-{i}", "name": name, "startedAt": i}))


def delivered(ctx, sid):
    out = run(ctx, "hook-deliver", event={"session_id": sid, "hook_event_name": "PostToolUse"}).stdout
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def test_private_message_starting_with_a_session_name_goes_to_that_session(ctx):
    with_sessions(ctx, "AutoEval Compare (R2V)", "AutoEval Bot (R2V)")
    assert "for AutoEval Compare (R2V)" in top(ctx, "om_a", "compare：GSB 那版跑完了吗")
    assert "for AutoEval Bot (R2V)" in top(ctx, "om_b", "@AutoEvalBot 看下群消息")
    text = delivered(ctx, "sid-0")
    assert "点名" in text and "GSB 那版跑完了吗" in text and "compare" not in text.lower()
    assert "看下群消息" in delivered(ctx, "sid-1")


def test_unnamed_or_stopped_session_gets_an_answer_from_the_hub_not_silence(ctx):
    with_sessions(ctx, "AutoEval Compare (R2V)")
    assert "names no session" in top(ctx, "om_c", "看下进度")
    assert "names no session" in top(ctx, "om_d", "comparex 看下进度")  # a name must end at a word boundary
    says = [c for c in calls(ctx) if "--text" in c["args"]]
    assert len(says) == 2 and "Compare" in says[0]["args"][says[0]["args"].index("--text") + 1]
    (ctx[1] / "config.json").write_text(json.dumps({"profile": "p", "chat_id": "oc_me", "user_open_id": USER,
                                                     "groups": {"oc_train": "Training (R2V)"}}))
    assert "not running" in top(ctx, "om_e", "在吗", chat="oc_train")


def test_message_in_a_session_group_goes_to_it_and_the_reply_is_a_plain_group_message(ctx, tmp_path):
    (ctx[1] / "config.json").write_text(json.dumps({"profile": "p", "chat_id": "oc_me", "user_open_id": USER,
                                                     "groups": {"oc_eval": "Eval (R2V)"}}))
    assert "ignored" in top(ctx, "om_f", "@_user_1 在吗", chat="oc_eval", sender="ou_someone_else")
    assert "ignored" in top(ctx, "om_g", "在吗", chat="oc_other")
    assert "for Eval (R2V)" in top(ctx, "om_h", "@_user_1 s550 评完了吗", chat="oc_eval")
    text = delivered(ctx, SID)
    assert "飞书群" in text and "s550 评完了吗" in text and "@_user" not in text
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"type": "assistant", "timestamp": "2999-01-01T00:00:00Z",
                                      "message": {"content": [{"type": "text", "text": "评完了，0.71"}]}}) + "\n")
    run(ctx, "hook-reply", event={"session_id": SID, "transcript_path": str(transcript)})
    post = [c for c in calls(ctx) if "+messages-reply" in c["args"]][-1]
    assert "--reply-in-thread" not in post["args"] and post["stdin"] == "评完了，0.71"


def test_groups_creates_one_group_per_running_session_once(ctx):
    with_sessions(ctx, "Training (R2V)")
    assert run(ctx, "groups").returncode == 0
    assert run(ctx, "groups").returncode == 0
    made = [c for c in calls(ctx) if "+chat-create" in c["args"]]
    assert sorted(c["args"][c["args"].index("--name") + 1] for c in made) == ["Eval (R2V)", "Training (R2V)"]
    assert set(json.loads((ctx[1] / "config.json").read_text())["groups"].values()) == {"Eval (R2V)", "Training (R2V)"}


# ---- Antigravity (agy) sessions ------------------------------------------------------------

CONV = "conv-agy"
AGY_QUESTIONS = [{"question": "午饭吃什么？", "is_multi_select": False, "options": ["(Recommended) 米饭", "面条"]}]
FAKE_AGENTAPI = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_AGENTAPI_LOG"], "a") as f:
    f.write(json.dumps({"args": sys.argv[1:], "ls": os.environ.get("ANTIGRAVITY_LS_ADDRESS"),
                        "csrf": os.environ.get("ANTIGRAVITY_CSRF_TOKEN")}, ensure_ascii=False) + "\\n")
print(json.dumps({"response": {"sendMessage": {"recipientId": sys.argv[-2]}}}))
"""


@pytest.fixture
def agy(ctx):
    tmp_path, root, env = ctx
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "tmux").write_text("#!/bin/sh\necho probe-r2v\n")
    (bin_dir / "tmux").chmod(0o755)
    api = tmp_path / "agentapi"
    api.write_text(FAKE_AGENTAPI)
    api.chmod(0o755)
    env = {**env, "PATH": f"{bin_dir}:{env['PATH']}", "TMUX_PANE": "%1", "FAKE_AGENTAPI_LOG": str(tmp_path / "api.jsonl"),
           "AGENT_ASK_AGY_PID": str(os.getpid()),  # one live "agy" for the whole test
           "AGENT_ASK_AGY_HOME": str(tmp_path / "agy-home")}
    return tmp_path, root, env


def under_agy(ctx, mode, event=None, env=None):
    """Run an agent-ask mode the way agy runs a hook or a command: as a descendant of the agy process."""
    cmd = f"{sys.executable} {SCRIPT} {mode}; :"  # the trailing no-op keeps sh from exec-ing python
    return subprocess.run(["bash", "-c", 'exec -a agy /bin/sh -c "$0"', cmd],  # an ancestor whose argv[0] is agy
                          input=json.dumps(event) if event is not None else "", capture_output=True, text=True,
                          env=env or ctx[2])


def agy_record(ctx):
    return json.loads((ctx[1] / "agy" / f"{CONV}.json").read_text())


def agy_start(ctx, env=None):
    return under_agy(ctx, "agy-session", {"conversationId": CONV, "hookEventName": "SessionStart"}, env)


def agy_register(ctx):
    env = {**ctx[2], "ANTIGRAVITY_CONVERSATION_ID": CONV, "ANTIGRAVITY_LS_ADDRESS": "localhost:5",
           "ANTIGRAVITY_CSRF_TOKEN": "tok", "ANTIGRAVITY_AGENTAPI_EXE": str(ctx[0] / "agentapi")}
    return under_agy(ctx, "agy-register", env=env)


def agy_ask(ctx):
    event = {"conversationId": CONV, "hookEventName": "PreToolUse", "cwd": "/x/proj",
             "toolCall": {"id": "call_1", "name": "ask_question", "args": {"questions": AGY_QUESTIONS}}}
    return under_agy(ctx, "agy-ask", event)


def hub_call(ctx, expr):
    code = (f"import importlib.machinery; m=importlib.machinery.SourceFileLoader('a',{str(SCRIPT)!r}).load_module();"
            f"{expr}")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=ctx[2])
    assert out.returncode == 0, out.stderr
    return out.stdout


def api_calls(ctx):
    path = ctx[0] / "api.jsonl"
    return [json.loads(line) for line in open(path)] if path.exists() else []


def test_agy_session_in_a_r2v_tmux_session_registers_and_learns_about_feishu(agy):
    out = json.loads(agy_start(agy).stdout)
    rec = agy_record(agy)
    assert rec["name"] == "Probe (R2V)" and rec["sessionId"] == CONV and not rec.get("csrf")
    hint = out["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "agent-ask agy-register" in hint and "ask_question" in hint
    env = {**agy[2]}
    (agy[0] / "bin/tmux").write_text("#!/bin/sh\necho scratch\n")
    assert json.loads(under_agy(agy, "agy-session", {"conversationId": "conv-2"}, env).stdout) == {}
    assert not (agy[1] / "agy" / "conv-2.json").exists()


def test_agy_question_goes_to_feishu_and_its_dialog_is_denied(agy):
    agy_start(agy)
    out = json.loads(agy_ask(agy).stdout)
    assert out["decision"] == "deny"
    rec = record(agy)
    assert rec["session"] == "Probe (R2V)" and rec["host"] == "agy"
    assert rec["questions"][0]["options"] == [{"label": "(Recommended) 米饭"}, {"label": "面条"}]
    card = json.loads(calls(agy)[0]["stdin"])
    assert "primary_filled" in json.dumps(card) and "**米饭**" in json.dumps(card, ensure_ascii=False)
    assert rec["qid"] in out["reason"] and "agent-ask agy-register" in out["reason"]  # not registered yet
    agy_register(agy)
    second = {"conversationId": CONV, "toolCall": {"id": "call_2", "name": "ask_question",
                                                    "args": {"questions": AGY_QUESTIONS}}}
    assert "agy-register" not in json.loads(under_agy(agy, "agy-ask", second).stdout)["reason"]


def test_agy_question_outside_scope_keeps_its_dialog(agy):
    (agy[0] / "bin/tmux").write_text("#!/bin/sh\necho scratch\n")  # not a *-r2v tmux session
    out = json.loads(agy_ask(agy).stdout)
    assert out["decision"] == "allow"
    assert not list((agy[1] / "questions").glob("*.json"))


def test_answer_is_pushed_into_the_agy_conversation_once(agy):
    agy_start(agy)
    agy_ask(agy)
    agy_register(agy)
    qid = record(agy)["qid"]
    click(agy, qid, 0, "(Recommended) 米饭")  # the hub pushes from the click itself
    assert not (agy[1] / "answered" / qid).exists()  # no marker: the Claude hooks never collect agy answers
    [sent] = api_calls(agy)
    assert sent["args"][:2] == ["agentapi", "send-message"] and sent["args"][2] == CONV
    assert "米饭" in sent["args"][3] and sent["ls"] == "localhost:5" and sent["csrf"] == "tok"
    assert record(agy)["status"] == "delivered"
    hub_call(agy, f"m.deliver_agy({CONV!r})")
    assert len(api_calls(agy)) == 1


def test_agy_thread_message_is_pushed_and_the_reply_goes_back(agy, tmp_path):
    agy_start(agy)
    agy_ask(agy)
    agy_register(agy)
    rec = record(agy)
    click(agy, rec["qid"], 0, "面条")
    hub_call(agy, f"m.deliver_agy({CONV!r})")
    assert "for Probe (R2V)" in message(agy, "om_u9", rec["message_id"], text="加个蛋")
    hub_call(agy, f"m.deliver_agy({CONV!r})")
    assert "加个蛋" in api_calls(agy)[-1]["args"][3]
    # The hook names transcript.jsonl, which shortens long steps; the reply comes from transcript_full.jsonl.
    step = {"type": "PLANNER_RESPONSE", "created_at": "2999-01-01T00:00:00Z"}
    (tmp_path / "transcript.jsonl").write_text(json.dumps({**step, "content": "好，"}, ensure_ascii=False) + "\n")
    (tmp_path / "transcript_full.jsonl").write_text(json.dumps({**step, "content": "好，加蛋"}, ensure_ascii=False) + "\n")
    under_agy(agy, "agy-reply", {"conversationId": CONV, "transcriptPath": str(tmp_path / "transcript.jsonl")})
    posts = [c for c in calls(agy) if "+messages-reply" in c["args"]]
    assert posts[-1]["args"][posts[-1]["args"].index("--message-id") + 1] == "om_u9"
    assert "好，加蛋" in posts[-1]["stdin"]


def test_agy_subagent_conversation_is_not_filed(agy):
    """A subagent shares its session's agy process and pane; filing it would take that session's messages."""
    import sqlite3
    home = Path(agy[2]["AGENT_ASK_AGY_HOME"])
    home.mkdir()
    with sqlite3.connect(home / "conversation_summaries.db") as db:
        db.execute("CREATE TABLE conversation_summaries (conversation_id text, parent_conversation_id text)")
        db.execute("INSERT INTO conversation_summaries VALUES ('sub-1', ?)", (CONV,))
    assert json.loads(under_agy(agy, "agy-session", {"conversationId": "sub-1"}).stdout) == {}
    assert not (agy[1] / "agy" / "sub-1.json").exists()
    agy_start(agy)  # the session itself still is
    assert agy_record(agy)["sessionId"] == CONV


def test_agy_session_start_drops_records_of_exited_sessions(agy):
    (agy[1] / "agy").mkdir(parents=True)
    (agy[1] / "agy" / "gone.json").write_text(json.dumps({"sessionId": "gone", "name": "Old (R2V)", "pid": 999999}))
    agy_start(agy)
    assert not (agy[1] / "agy" / "gone.json").exists() and (agy[1] / "agy" / f"{CONV}.json").exists()


def test_agy_session_counts_as_live_for_routing(agy):
    agy_start(agy)
    agy_register(agy)
    assert "Probe (R2V)" in json.loads(hub_call(agy, "import json; print(json.dumps(m.live_sessions()))"))


def test_agy_session_is_found_by_its_agy_ancestor(agy):
    env = {k: v for k, v in agy[2].items() if k != "AGENT_ASK_AGY_PID"}
    under_agy(agy, "agy-session", {"conversationId": CONV}, env)
    assert isinstance(agy_record(agy)["pid"], int)
    plain = run(agy, "agy-session", event={"conversationId": "conv-3"}, env=env)  # no agy above it
    assert json.loads(plain.stdout) == {} and not (agy[1] / "agy" / "conv-3.json").exists()


def test_resumed_agy_conversation_drops_the_old_process_token(agy):
    agy_start(agy)
    agy_register(agy)
    resumed = {**agy[2], "AGENT_ASK_AGY_PID": str(os.getppid())}  # another live process: the resumed agy
    out = json.loads(under_agy(agy, "agy-ask", {"conversationId": CONV, "toolCall": {
        "id": "call_9", "name": "ask_question", "args": {"questions": AGY_QUESTIONS}}}, resumed).stdout)
    assert "agent-ask agy-register" in out["reason"]  # the old token died with the old process
    rec = agy_record(agy)
    assert rec["pid"] == os.getppid() and "csrf" not in rec


def test_agy_push_marks_only_the_messages_it_carried(agy):
    agy_start(agy)
    agy_ask(agy)
    agy_register(agy)
    rec = record(agy)
    message(agy, "om_a", rec["message_id"], text="第一条")
    # A second message lands while the push is on its way: the push must leave it pending.
    hub_call(agy, "orig = m.inbox_items\n"
                  "def snapshot():\n"
                  "    items = orig()\n"
                  "    m.inbox_items = orig\n"
                  "    m.save_item({**items[0], 'message_id': 'om_b', 'text': '推送时新到的', 'status': 'pending'})\n"
                  "    return items\n"
                  "m.inbox_items = snapshot\n"
                  f"m.deliver_agy({CONV!r})")
    items = {json.loads(p.read_text())["message_id"]: json.loads(p.read_text())["status"]
             for p in (agy[1] / "inbox").glob("*.json")}
    assert items == {"om_a": "delivered", "om_b": "pending"}  # om_b arrived during the push: still to send
    assert "第一条" in api_calls(agy)[-1]["args"][3] and "推送时新到的" not in api_calls(agy)[-1]["args"][3]


def test_agy_reply_reads_only_agent_replies(agy, tmp_path):
    agy_start(agy)
    agy_ask(agy)
    agy_register(agy)
    rec = record(agy)
    message(agy, "om_c", rec["message_id"], text="几点？")
    hub_call(agy, f"m.deliver_agy({CONV!r})")
    transcript = tmp_path / "transcript_full.jsonl"
    transcript.write_text(json.dumps({"type": "USER_INPUT", "created_at": "2999-01-01T00:00:00Z",
                                      "content": "grep PLANNER_RESPONSE 的输出"}, ensure_ascii=False) + "\n")
    under_agy(agy, "agy-reply", {"conversationId": CONV, "transcriptPath": str(transcript)})
    assert not [c for c in calls(agy) if "+messages-reply" in c["args"]]
