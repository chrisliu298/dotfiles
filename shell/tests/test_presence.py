import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "presence"
SID = "8590b7f3-52fd-46ec-93e4-1780ef20fd03"
OTHER = "a0376d57-3bdd-449d-b054-36541bd1087b"


@pytest.fixture
def context(tmp_path):
    root = tmp_path / ".local/state/presence"
    root.mkdir(parents=True)
    project = tmp_path / "project"
    project.mkdir()
    (root / "projects").write_text(str(project) + "\n")
    (root / "sessions").write_text(SID + "\n" + OTHER + "\n")
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL") if k in os.environ}
    env.update(HOME=str(tmp_path), XDG_STATE_HOME=str(tmp_path / ".local/state"))
    return root, project, env


def call(context, *args, event=None, agent=None):
    _, project, env = context
    if agent:
        env = dict(env, **agent)
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=json.dumps(event) if event else None,
                          capture_output=True, text=True, env=env, cwd=project)


def event(context, sid=SID, **extra):
    return dict(session_id=sid, cwd=str(context[1]), source="user") | extra


def questions(*texts):
    return {"questions": [{"question": t, "header": "Choice", "options": [{"label": "A"}, {"label": "B"}]} for t in texts]}


def test_manual_switch_idempotent_and_agent_cannot_switch(context):
    assert call(context, "away", "18:00").returncode == 0
    path = context[0] / "state.json"
    before = path.read_bytes()
    assert call(context, "away", "different").returncode == 0
    assert path.read_bytes() == before
    for agent in ({"CLAUDECODE": "1"}, {"CODEX_THREAD_ID": "thread"}):
        assert call(context, "back", agent=agent).returncode != 0
        assert path.read_bytes() == before
    assert call(context, "back").returncode == 0
    assert json.loads(path.read_text())["state"] == "present"


def test_away_queues_only_configured_sessions_and_no_cli_disclosure(context):
    call(context, "away")
    e = event(context, tool_name="AskUserQuestion", tool_input=questions("Run this?"))
    result = call(context, "hook-ask", event=e, agent={"CLAUDECODE": "1"})
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "presence" not in result.stdout and "~/." not in result.stdout
    queued = json.loads((context[0] / "questions" / (SID + ".json")).read_text())
    assert len(queued["items"]) == 1
    call(context, "hook-ask", event=e)
    assert len(json.loads((context[0] / "questions" / (SID + ".json")).read_text())["items"]) == 1
    assert call(context, "hook-ask", event=event(context, sid="temporary", tool_input=questions("Ignore?"))).stdout == ""
    assert not (context[0] / "questions/temporary.json").exists()
    outside = dict(e, cwd="/outside")
    assert call(context, "hook-ask", event=outside).stdout == ""


def test_checkin_grace_and_peer_does_not_checkin(context):
    call(context, "away")
    call(context, "hook-prompt", event=event(context, prompt="<cross-session-message>ping"))
    assert not (context[0] / "seen" / SID).exists()
    prompt = call(context, "hook-prompt", event=event(context, prompt="I am checking this window"))
    assert "presence" not in prompt.stdout and "back" not in prompt.stdout
    assert json.loads((context[0] / "state.json").read_text())["state"] == "away"
    assert call(context, "hook-ask", event=event(context, tool_input=questions("Now?"))).stdout == ""
    blocked = call(context, "hook-ask", event=event(context, sid=OTHER, tool_input=questions("Later?")))
    assert json.loads(blocked.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("source", ["system", "sdk", "loop_wakeup", "schedule_wakeup", "poll_event"])
def test_automatic_prompt_cannot_open_or_refresh_checkin(context, source):
    call(context, "away")
    seen = context[0] / "seen" / SID
    seen.parent.mkdir()
    seen.write_text("0")
    call(context, "hook-prompt", event=event(context, source=source, prompt="Training 巡检：回读任务状态。"))
    assert seen.read_text() == "0"
    blocked = call(context, "hook-ask", event=event(context, tool_input=questions("Submit?")))
    assert json.loads(blocked.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("prompt", ["[peer] agent-msg read probe", "Another Claude session on this machine sent you a message: ping"])
def test_terminal_peer_prompt_does_not_checkin(context, prompt):
    call(context, "away")
    transcript = context[1] / "session.jsonl"
    record = dict(type="user", sessionId=SID, promptId="peer-input", turnOrigin="human", promptSource="queued",
                  timestamp=datetime.now(timezone.utc).isoformat(), message={"role": "user", "content": prompt})
    transcript.write_text(json.dumps(record) + "\n")
    e = event(context, prompt=prompt, prompt_id="peer-input", transcript_path=str(transcript))
    call(context, "hook-prompt", event=e)
    blocked = call(context, "hook-ask", event=dict(e, tool_input=questions("Submit?")))
    assert json.loads(blocked.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not (context[0] / "seen" / SID).exists()


@pytest.mark.parametrize("origin,source,meta,allowed", [
    ("scheduled", "system", True, False),
    ("peer", "system", True, False),
    ("task_notification", "system", False, False),
    ("human", "typed", False, True),
    ("human", "queued", False, True),
    ("human", "suggestion_accepted", False, True),
])
def test_legacy_prompt_without_source_uses_own_transcript_origin(context, origin, source, meta, allowed):
    call(context, "away")
    transcript = context[1] / "session.jsonl"
    previous = dict(type="user", sessionId=SID, promptId="previous", turnOrigin="human", promptSource="typed")
    current = dict(type="user", sessionId=SID, promptId="current", turnOrigin=origin, promptSource=source,
                   isMeta=meta, timestamp=datetime.now(timezone.utc).isoformat(),
                   message={"role": "user", "content": "Training 巡检：回读任务状态。"})
    if origin == "scheduled":
        current["wakeupSource"] = "schedule_wakeup"
    # A later tool result shares the prompt ID; it is not evidence of human input.
    result = dict(type="user", sessionId=SID, promptId="current",
                  message={"role": "user", "content": [{"type": "tool_result", "content": "done"}]})
    transcript.write_text("\n".join(json.dumps(r) for r in [previous, current, result]) + "\n")
    call(context, "hook-prompt", event=event(context, source=None, prompt_id="current", transcript_path=str(transcript),
                                            prompt="Training 巡检：回读任务状态。"))
    assert (context[0] / "seen" / SID).exists() is allowed
    asked = call(context, "hook-ask", event=event(context, tool_input=questions("Submit?")))
    assert (asked.stdout == "") is allowed


@pytest.mark.parametrize("kind", ["missing", "unmatched", "other-session", "invalid"])
def test_unknown_origin_does_not_assume_user_is_present(context, kind):
    call(context, "away")
    transcript = context[1] / "session.jsonl"
    if kind != "missing":
        record = dict(type="user", sessionId=OTHER if kind == "other-session" else SID,
                      promptId="previous" if kind == "unmatched" else "current", turnOrigin="human",
                      promptSource="typed", message={"role": "user", "content": "Hello"})
        transcript.write_text("not json\n" if kind == "invalid" else json.dumps(record) + "\n")
    call(context, "hook-prompt", event=event(context, source=None, prompt_id="current", transcript_path=str(transcript), prompt="Hello"))
    assert not (context[0] / "seen" / SID).exists()


@pytest.mark.parametrize("origin,age,allowed", [("human", 30, True), ("human", 960, False),
                                               ("scheduled", 30, False), ("peer", 30, False)])
def test_origin_can_be_verified_after_prompt_is_written(context, origin, age, allowed):
    call(context, "away")
    call(context, "hook-ask", event=event(context, tool_input=questions("Pending?")))
    transcript = context[1] / "session.jsonl"
    e = event(context, source=None, prompt_id="current", transcript_path=str(transcript), prompt="Continue")
    prompt = call(context, "hook-prompt", event=e)
    assert "Pending?" in prompt.stdout
    assert "15 分钟" not in prompt.stdout
    assert not (context[0] / "seen" / SID).exists()
    at = time.time() - age
    record = dict(type="user", sessionId=SID, promptId="current", turnOrigin=origin,
                  promptSource="typed" if origin == "human" else "system",
                  timestamp=datetime.fromtimestamp(at, timezone.utc).isoformat(),
                  message={"role": "user", "content": "Continue"})
    transcript.write_text(json.dumps(record) + "\n")
    asked = call(context, "hook-ask", event=dict(e, tool_input=questions("Pending?")))
    assert (asked.stdout == "") is allowed
    if allowed:
        # Repeated questions do not extend grace beyond the original human input.
        first = (context[0] / "seen" / SID).read_text()
        call(context, "hook-ask", event=dict(e, tool_input=questions("Another?")))
        assert (context[0] / "seen" / SID).read_text() == first
        assert abs(float(first) - at) < 0.01
    else:
        assert json.loads(asked.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_large_tool_output_does_not_hide_current_human_input(context):
    call(context, "away")
    transcript = context[1] / "session.jsonl"
    e = event(context, source=None, prompt_id="current", transcript_path=str(transcript), prompt="Continue")
    call(context, "hook-prompt", event=e)
    record = dict(type="user", sessionId=SID, promptId="current", turnOrigin="human", promptSource="typed",
                  timestamp=datetime.now(timezone.utc).isoformat(), message={"role": "user", "content": "Continue"})
    output = dict(type="api-request", data="x" * (2 * 1024 * 1024))
    transcript.write_text(json.dumps(record) + "\n" + json.dumps(output) + "\n")
    asked = call(context, "hook-ask", event=dict(e, tool_input=questions("Submit?")))
    assert asked.stdout == ""


@pytest.mark.parametrize("prompt_id", ["scheduled-turn", "fresh-id"])
@pytest.mark.parametrize("origin,prompt,allowed", [("human", "我回来了，有问题直接问", True),
                                                ("human", "[peer] agent-msg read reply", False),
                                                ("peer", "A peer message", False)])
def test_midturn_input_uses_native_queued_origin(context, prompt_id, origin, prompt, allowed):
    call(context, "away")
    transcript = context[1] / "session.jsonl"
    original = dict(type="user", sessionId=SID, promptId="scheduled-turn", isMeta=True,
                    promptSource="system", wakeupSource="schedule_wakeup", turnOrigin="scheduled",
                    message={"role": "user", "content": "Training 巡检"})
    queued = dict(type="attachment", sessionId=SID, timestamp=datetime.now(timezone.utc).isoformat(),
                  attachment={"type": "queued_command", "commandMode": "prompt", "origin": {"kind": origin}, "prompt": prompt})
    transcript.write_text(json.dumps(original) + "\n" + json.dumps(queued) + "\n")
    e = event(context, source=None, prompt_id=prompt_id, transcript_path=str(transcript), prompt=prompt)
    call(context, "hook-prompt", event=e)
    asked = call(context, "hook-ask", event=dict(e, tool_input=questions("Submit?")))
    assert (asked.stdout == "") is allowed


def test_recovering_original_input_never_shortens_a_later_checkin(context):
    call(context, "away")
    call(context, "hook-prompt", event=event(context, prompt="A recent human input"))
    seen = context[0] / "seen" / SID
    recent = seen.read_text()
    transcript = context[1] / "session.jsonl"
    record = dict(type="user", sessionId=SID, promptId="original", turnOrigin="human", promptSource="typed",
                  timestamp=datetime.fromtimestamp(time.time() - 890, timezone.utc).isoformat(),
                  message={"role": "user", "content": "An earlier input"})
    transcript.write_text(json.dumps(record) + "\n")
    e = event(context, source=None, prompt_id="original", transcript_path=str(transcript), tool_input=questions("Now?"))
    assert call(context, "hook-ask", event=e).stdout == ""
    assert seen.read_text() == recent


def test_delayed_midturn_attachment_still_shows_pending_questions(context):
    call(context, "away")
    call(context, "hook-ask", event=event(context, tool_input=questions("Pending?")))
    transcript = context[1] / "session.jsonl"
    original = dict(type="user", sessionId=SID, promptId="original", promptSource="system",
                    turnOrigin="scheduled", isMeta=True, message={"role": "user", "content": "Automatic patrol"})
    transcript.write_text(json.dumps(original) + "\n")
    e = event(context, source=None, prompt_id="original", transcript_path=str(transcript), prompt="我回来了")
    result = call(context, "hook-prompt", event=e)
    assert "Pending?" in result.stdout
    assert not (context[0] / "seen" / SID).exists()
    queued = dict(type="attachment", sessionId=SID, timestamp=datetime.now(timezone.utc).isoformat(),
                  attachment={"type": "queued_command", "commandMode": "prompt", "origin": {"kind": "human"}, "prompt": "我回来了"})
    with transcript.open("a") as out:
        out.write(json.dumps(queued) + "\n")
    assert call(context, "hook-ask", event=dict(e, tool_input=questions("Pending?"))).stdout == ""


@pytest.mark.parametrize("age,text,allowed", [(7200, "A screenshot", False), (30, "A screenshot", True),
                                            (30, "[peer] agent-msg read reply", False)])
def test_image_midturn_input_is_normalized_and_expired_input_stays_blocked(context, age, text, allowed):
    call(context, "away")
    transcript = context[1] / "session.jsonl"
    content = [{"type": "text", "text": text}, {"type": "image", "source": {"type": "base64", "data": ""}}]
    queued = dict(type="attachment", sessionId=SID,
                  timestamp=datetime.fromtimestamp(time.time() - age, timezone.utc).isoformat(),
                  attachment={"type": "queued_command", "commandMode": "prompt", "origin": {"kind": "human"}, "prompt": content})
    transcript.write_text(json.dumps(queued) + "\n")
    e = event(context, source=None, prompt_id="original", transcript_path=str(transcript), prompt=text)
    prompt = call(context, "hook-prompt", event=e)
    asked = call(context, "hook-ask", event=dict(e, tool_input=questions("Submit?")))
    assert prompt.stderr == asked.stderr == ""
    assert (asked.stdout == "") is allowed


@pytest.mark.parametrize("human_kind", ["ordinary", "midturn"])
def test_later_notification_does_not_hide_recent_human_input(context, human_kind):
    call(context, "away")
    transcript = context[1] / "session.jsonl"
    e = event(context, source=None, prompt_id="current", transcript_path=str(transcript), prompt="Continue")
    call(context, "hook-prompt", event=e)
    at = datetime.now(timezone.utc).isoformat()
    if human_kind == "ordinary":
        human = dict(type="user", sessionId=SID, promptId="current", timestamp=at, turnOrigin="human", promptSource="typed",
                     message={"role": "user", "content": "Continue"})
    else:
        human = dict(type="attachment", sessionId=SID, timestamp=at,
                     attachment={"type": "queued_command", "commandMode": "prompt", "origin": {"kind": "human"}, "prompt": "Continue"})
    notification = dict(type="attachment", sessionId=SID, timestamp=at,
                        attachment={"type": "queued_command", "commandMode": "prompt", "origin": {"kind": "task-notification"}, "prompt": "Finished"})
    transcript.write_text(json.dumps(human) + "\n" + json.dumps(notification) + "\n")
    assert call(context, "hook-ask", event=dict(e, tool_input=questions("Submit?"))).stdout == ""


def test_return_shows_own_queue_and_answer_removes_only_answered(context):
    call(context, "away")
    call(context, "hook-ask", event=event(context, tool_input=questions("First?", "Second?")))
    call(context, "back")
    prompt = call(context, "hook-prompt", event=event(context, prompt="Continue"))
    assert "First?" in prompt.stdout and "Second?" in prompt.stdout
    assert "presence" not in prompt.stdout and "resolved" not in prompt.stdout
    call(context, "hook-post", event=event(context, tool_name="AskUserQuestion", tool_input=questions("First?"),
                                         tool_response={"answers": {"First?": "A"}}))
    queue = json.loads((context[0] / "questions" / (SID + ".json")).read_text())
    assert len(queue["items"]) == 1 and queue["items"][0]["question"] == "Second?"
    call(context, "hook-post", event=event(context, tool_name="AskUserQuestion", tool_input=questions("Second?"), tool_response={}))
    assert (context[0] / "questions" / (SID + ".json")).exists()


def test_manual_view_and_removed_management_commands(context):
    call(context, "away")
    call(context, "hook-ask", event=event(context, tool_input=questions("One?")))
    assert "One?" in call(context, "questions").stdout
    assert call(context, "ask", "One?").returncode != 0
    assert call(context, "resolved", "--session", SID, "1").returncode != 0
    assert (context[0] / "questions" / (SID + ".json")).exists()


def test_rephrased_answer_uses_queue_identity_and_keeps_other_questions(context):
    call(context, "away")
    call(context, "hook-ask", event=event(context, tool_input=questions("Original?", "Other?")))
    path = context[0] / "questions" / (SID + ".json")
    queued = json.loads(path.read_text())
    key = queued["items"][0]["key"]
    prompt = call(context, "hook-prompt", event=event(context, prompt="Back here"))
    assert "待问-" + key in prompt.stdout
    rewritten = questions("Original, with more context?")
    rewritten["questions"][0]["header"] = "待问-" + key
    call(context, "hook-post", event=event(context, tool_name="AskUserQuestion", tool_input=rewritten,
                                         tool_response={"answers": {"Original, with more context?": "A"}}))
    assert [i["question"] for i in json.loads(path.read_text())["items"]] == ["Other?"]


def test_corrected_question_deferred_again_keeps_identity_until_answered(context):
    call(context, "away")
    original = questions("Original premise?")
    call(context, "hook-ask", event=event(context, tool_name="AskUserQuestion", tool_input=original))
    path = context[0] / "questions" / (SID + ".json")
    first = json.loads(path.read_text())["items"][0]
    corrected = questions("The premise was wrong; choose a corrected plan?")
    corrected["questions"][0]["header"] = "待问-" + first["key"]
    deferred = call(context, "hook-ask", event=event(context, tool_name="AskUserQuestion", tool_input=corrected))
    assert json.loads(deferred.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    items = json.loads(path.read_text())["items"]
    assert len(items) == 1
    assert (items[0]["id"], items[0]["key"], items[0]["at"]) == (first["id"], first["key"], first["at"])
    assert items[0]["question"] == corrected["questions"][0]["question"]
    call(context, "back")
    call(context, "hook-prompt", event=event(context, prompt="Ask the pending question"))
    final = questions("A concise version of the corrected plan?")
    final["questions"][0]["header"] = "待问-" + first["key"]
    assert call(context, "hook-ask", event=event(context, tool_name="AskUserQuestion", tool_input=final)).stdout == ""
    call(context, "hook-post", event=event(context, tool_name="AskUserQuestion", tool_input=final,
                                         tool_response={"questions": final["questions"], "answers": {final["questions"][0]["question"]: "A"}}))
    assert not path.exists()


def test_corrected_requeue_keeps_unrelated_items_and_cancellation(context):
    call(context, "away")
    call(context, "hook-ask", event=event(context, tool_input=questions("First?", "Unrelated?")))
    path = context[0] / "questions" / (SID + ".json")
    before = json.loads(path.read_text())["items"]
    batch = questions("Corrected first?", "New question?")
    batch["questions"][0]["header"] = "待问-" + before[0]["key"]
    call(context, "hook-ask", event=event(context, tool_input=batch))
    items = json.loads(path.read_text())["items"]
    assert len(items) == 3
    assert items[1] == before[1]
    assert items[0]["key"] == before[0]["key"]
    call(context, "hook-post", event=event(context, tool_name="AskUserQuestion", tool_input=batch,
                                         tool_response={"answers": {"Corrected first?": "", "New question?": "A"}}))
    remaining = json.loads(path.read_text())["items"]
    assert [item["key"] for item in remaining] == [before[0]["key"], before[1]["key"]]


def test_old_queue_gets_stable_identity_and_cancel_does_not_remove(context):
    path = context[0] / "questions" / (SID + ".json")
    path.parent.mkdir()
    path.write_text(json.dumps({"items": [{"id": 1, "at": "2026-11-08T00:00:00+0800",
                                           "text": "Legacy?", "question": "Legacy?"}]}))
    call(context, "hook-prompt", event=event(context, prompt="Back"))
    key = json.loads(path.read_text())["items"][0]["key"]
    call(context, "hook-prompt", event=event(context, prompt="Again"))
    assert json.loads(path.read_text())["items"][0]["key"] == key
    rewritten = questions("Reworded legacy?")
    rewritten["questions"][0]["header"] = "待问-" + key
    call(context, "hook-post", event=event(context, tool_name="AskUserQuestion", tool_input=rewritten,
                                         tool_response={"answers": {"Reworded legacy?": ""}}))
    assert json.loads(path.read_text())["items"]
    rewritten["questions"][0]["header"] = "待问-not-the-key"
    call(context, "hook-post", event=event(context, tool_name="AskUserQuestion", tool_input=rewritten,
                                         tool_response={"answers": {"Reworded legacy?": "A"}}))
    assert json.loads(path.read_text())["items"]


def test_stale_identity_cannot_remove_a_new_question_with_reused_display_id(context):
    call(context, "away")
    call(context, "hook-ask", event=event(context, tool_input=questions("Same words?")))
    path = context[0] / "questions" / (SID + ".json")
    old_key = json.loads(path.read_text())["items"][0]["key"]
    answered = {"answers": {"Same words?": "A"}}
    call(context, "hook-post", event=event(context, tool_name="AskUserQuestion",
                                         tool_input=questions("Same words?"), tool_response=answered))
    assert not path.exists()
    call(context, "hook-ask", event=event(context, tool_input=questions("Same words?")))
    new_item = json.loads(path.read_text())["items"][0]
    assert new_item["id"] == 1 and new_item["key"] != old_key
    stale = questions("Same words?")
    stale["questions"][0]["header"] = "待问-" + old_key
    call(context, "hook-post", event=event(context, tool_name="AskUserQuestion",
                                         tool_input=stale, tool_response=answered))
    assert json.loads(path.read_text())["items"] == [new_item]


def test_installer_keeps_state_and_limits_scope(context):
    root, _, env = context
    home = Path(env["HOME"])
    (root / "questions").mkdir()
    (root / "questions" / (SID + ".json")).write_text('{"items":[{"id":7,"text":"keep"}]}')
    registry = home / ".local/state/rex-claude/sessions"
    registry.mkdir(parents=True)
    (registry / "training-r2v.json").write_text(json.dumps({"transport": "rex", "sessionId": SID, "cwd": str(context[1])}))
    (registry / "lead-r2v.json").write_text(json.dumps({"transport": "retired", "sessionId": OTHER}))
    (root / "state.json").write_text('{"state":"present","since":"newer"}')
    installer = SCRIPT.parents[1] / "dotfiles.sh"
    result = subprocess.run(["bash", "-c", 'source "$1"; setup_presence_state', "check", str(installer)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads((root / "state.json").read_text())["since"] == "newer"
    assert json.loads((root / "questions" / (SID + ".json")).read_text())["items"][0]["id"] == 7
    assert (root / "sessions").read_text().strip() == SID
    assert (root / "projects").read_text().strip() == str(context[1])
    assert (home / ".local/bin/presence").resolve() == SCRIPT
    (root / "questions" / (SID + ".json")).unlink()
    repeated = subprocess.run(["bash", "-c", 'source "$1"; setup_presence_state', "check", str(installer)],
                              env=env, capture_output=True, text=True)
    assert repeated.returncode == 0, repeated.stderr
    assert not (root / "questions" / (SID + ".json")).exists()


def test_queue_keeps_full_question_and_shows_it_back(context):
    call(context, "away")
    full = {"question": "Which layout?", "header": "Layout", "multiSelect": True,
            "options": [{"label": "Grid", "description": "Two columns, denser", "preview": "+--+--+\n|a |b |"},
                        {"label": "List", "description": "One column"}]}
    call(context, "hook-ask", event=event(context, tool_input={"questions": [full]}))
    item = json.loads((context[0] / "questions" / (SID + ".json")).read_text())["items"][0]
    assert item["request"] == full
    call(context, "back")
    for shown in (call(context, "questions").stdout, call(context, "hook-prompt", event=event(context, prompt="Hi")).stdout):
        for part in ("Which layout?", "Layout", "多选", "Grid", "Two columns, denser", "|a |b |", "List", "One column"):
            assert part in shown, (part, shown)
