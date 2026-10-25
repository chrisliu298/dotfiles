import json
import os
import subprocess
import sys

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "agent-audit")
SID = "11111111-2222-3333-4444-555555555555"
CRON = "Lead check-in: read back jobs"


def rec(**kw):
    kw.setdefault("timestamp", "2026-10-20T02:00:00Z")
    return kw


def user(text, origin=None, meta=False, **kw):
    r = rec(type="user", message={"role": "user", "content": text}, **kw)
    if origin:
        r["origin"] = {"kind": origin}
    if meta:
        r["isMeta"] = True
    return r


def queued(prompt, kind):
    return rec(type="attachment", attachment={"type": "queued_command", "prompt": prompt, "origin": {"kind": kind},
                                               "timestamp": "2026-10-21T02:00:00Z"})


def tool_use(name, inp):
    return rec(type="assistant", message={"content": [{"type": "tool_use", "name": name, "input": inp}]})


@pytest.fixture
def projects(tmp_path):
    proj = tmp_path / "-Users-me-repo"
    proj.mkdir()
    peer = '<cross-session-message from="uds:/x.sock" from-name="Eval (R2V)">scores ready</cross-session-message>'
    lines = [
        {"type": "custom-title", "customTitle": "Lead (R2V)"},
        user("plan the next run", origin="human"),
        queued("also check priorities", "human"),
        queued("Another Claude session sent a message:\n" + peer, "peer"),
        user("Another Claude session sent a message:\n" + peer, origin="peer", meta=True),
        tool_use("CronCreate", {"cron": "*/30 * * * *", "prompt": CRON}),
        user(CRON, meta=True),
        user(CRON, meta=True),
        user("<local-command-caveat>ignored</local-command-caveat>", meta=True),
        queued("<task-notification><status>completed</status></task-notification>", "task-notification"),
        user("This session is being continued from a previous conversation."),
        rec(type="user", message={"content": [{"type": "tool_result", "content": "ok"}]}),
        user("in sidechain", origin="human", isSidechain=True),
        tool_use("SendMessage", {"to": "Eval (R2V)", "message": "rescore s400"}),
        tool_use("Agent", {"subagent_type": "Explore", "prompt": "find"}),
        tool_use("Skill", {"skill": "agent-team"}),
        tool_use("Bash", {"command": "cx start fix --effort low < t.md"}),
    ]
    (proj / f"{SID}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    sub = proj / SID / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-a.jsonl").write_text(json.dumps(tool_use("Edit", {"file_path": "/Users/me/repo/x.py"})) + "\n")
    (sub / "agent-b.jsonl").write_text(json.dumps(tool_use("Write", {"file_path": "/private/tmp/scratch.md"})) + "\n")
    cx = tmp_path / "cx" / "line1"
    cx.mkdir(parents=True)
    for f in ["msg-001.md", "msg-002.md", "reply-001.md", "ask-001.md", "ask-001.md.sent"]:
        (cx / f).write_text("x")
    return tmp_path


def run(projects, *args):
    env = dict(os.environ, AGENT_AUDIT_PROJECTS=str(projects), AGENT_AUDIT_CX=str(projects / "cx"), TZ="UTC")
    out = subprocess.run([sys.executable, SCRIPT, *args, "--json"], env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_sources_counts_each_delivery_once(projects):
    [row] = run(projects, "sources")
    assert row["key"] == "Lead (R2V)"
    # plain + queued human; queued + plain peer are separate deliveries; two cron fires.
    assert (row["user"], row["peer"], row["scheduled"], row["task-receipt"], row["compaction"], row["system"]) == (2, 2, 2, 1, 1, 1)


def test_sources_by_day_and_window(projects):
    rows = run(projects, "sources", "--by", "day")
    assert [r["key"] for r in rows] == ["2026-10-20", "2026-10-21"]
    [row] = run(projects, "sources", "--since", "2026-10-21")
    assert (row["user"], row["peer"], row["task-receipt"]) == (1, 1, 1)


def test_traffic(projects):
    assert run(projects, "traffic") == [{"from": "Lead (R2V)", "to": "Eval (R2V)", "messages": 1, "chars": 12}]


def test_delegation(projects):
    m = {r["metric"]: r["count"] for r in run(projects, "delegation", "--cx")}
    assert m["agent:Explore"] == 1 and m["skill:agent-team"] == 1 and m["bash:cx start"] == 1
    assert m["subagents"] == 2 and m["subagents editing non-scratch files"] == 1
    assert m["cx:line1"] == "msgs=2 replies=1 asks=1"
