import json
import os
import subprocess
import sys
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
    return dict(session_id=sid, cwd=str(context[1]), **extra)


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
