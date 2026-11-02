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


def ask(tid, ts):
    return rec(type="assistant", timestamp=ts, message={"content": [
        {"type": "tool_use", "id": tid, "name": "AskUserQuestion", "input": {"questions": []}}]})


def result(tid, ts, is_error=False):
    return rec(type="user", timestamp=ts, message={"content": [
        {"type": "tool_result", "tool_use_id": tid, "content": "x", "is_error": is_error}]})


def write_session(root, sid, title, lines):
    proj = root / "-Users-me-repo"
    proj.mkdir(exist_ok=True)
    body = [{"type": "custom-title", "customTitle": title}, *lines]
    (proj / f"{sid}.jsonl").write_text("\n".join(json.dumps(x) for x in body) + "\n")


@pytest.fixture
def attention(tmp_path):
    write_session(tmp_path, "aaaaaaaa-0000", "Lead (R2V)", [
        user("训练任务都排上了吗？", origin="human"),
        user("我指的是排队，不是排上", origin="human"),
        user("帮我写周报", origin="human"),
        user("<command-name>/now</command-name> 现在怎么样", origin="human"),
        user("<pasted_content id=\"x\">现在进度怎么样</pasted_content>看下这段", origin="human"),
        user("现在进度怎么样", origin="peer"),
        user("不对", origin="human", isSidechain=True),
        user("[Request interrupted by user]"),
        tool_use("SendMessage", {"to": "Training (R2V)", "message": "用户问：P 池什么时候训完？"}),
        tool_use("SendMessage", {"to": "Training (R2V)", "message": "优先级不变"}),
        tool_use("SendMessage", {"to": "Eval (R2V)", "message": "用户问：打分呢"}),
    ])
    write_session(tmp_path, "bbbbbbbb-0000", "Training (R2V)", [
        user("loss 为什么涨", origin="human"),
        ask("t1", "2026-10-20T03:00:00Z"), result("t1", "2026-10-20T03:10:00Z"),
        ask("t2", "2026-10-20T04:00:00Z"), result("t2", "2026-10-20T04:30:00Z"),
        ask("t3", "2026-10-20T05:00:00Z"), result("t3", "2026-10-20T05:00:01Z", is_error=True),
        ask("t4", "2026-10-20T06:00:00Z"),
        tool_use("Bash", {"command": "~/.claude/presence/presence ask 'A 还是 B？'"}),
    ])
    return tmp_path


def test_attention_classifies_only_the_users_own_words(attention):
    rows = {r["key"]: r for r in run(attention, "attention")}
    lead = rows["Lead (R2V)"]
    # The slash command, pasted text, peer and sidechain records never classify as the user's words.
    assert (lead["user"], lead["followup"], lead["correction"], lead["interrupt"]) == (5, 1, 1, 1)
    assert lead["relayed"] == 1
    assert rows["Training (R2V)"]["user"] == 1


def test_attention_times_answered_questions_only(attention):
    row = {r["key"]: r for r in run(attention, "attention")}["Training (R2V)"]
    # t3 was refused and t4 is unanswered: asked, but neither is a wait the user caused.
    assert (row["asked"], row["answered"], row["queued"]) == (4, 2, 1)
    assert (row["wait_median_min"], row["wait_total_min"]) == (20.0, 40.0)


def test_attention_by_day_and_list(attention):
    [row] = run(attention, "attention", "--by", "day")
    assert row["key"] == "2026-10-20" and row["user"] == 6
    listed = run(attention, "attention", "--list", "correction")
    assert [r["text"] for r in listed] == ["我指的是排队，不是排上"]


def test_attention_ignores_pasted_text_with_an_id_on_both_tags(tmp_path):
    write_session(tmp_path, "cccccccc-0000", "Lead (R2V)", [
        user('<pasted_content id="1">现在进度怎么样，你搞错了</pasted_content id="1">看下这段', origin="human"),
    ])
    [row] = run(tmp_path, "attention")
    assert (row["user"], row["followup"], row["correction"]) == (1, 0, 0)


def test_attention_separates_automated_prompts_and_keeps_the_sources_total(tmp_path):
    write_session(tmp_path, "dddddddd-0000", "Lead (R2V)", [
        user("# 任务：提出优化策略，你是独立的提案方", origin="human"),
        user("这个会话刚被重启了（tmux-persist restart）", origin="human"),
        user("你是新的 Lead (R2V)。请读 brief", origin="human"),
        queued([{"type": "text", "text": "现在进度怎么样了"}], "human"),
    ])
    [row] = run(tmp_path, "attention")
    assert (row["user"], row["automated"], row["followup"]) == (1, 3, 1)
    assert run(tmp_path, "sources")[0]["user"] == row["user"] + row["automated"]


@pytest.mark.parametrize("text,kind", [
    ("什么时候可以全部上线？", "followup"), ("取证工具 bug 还没修复？", "followup"), ("几点能上线", "followup"),
    ("跑完了马上告诉我结果", None), ("你可能误解了，还有什么不清楚的", "correction"), ("我指的是图整体小一点", "correction"),
    ("这个顺序不对吧", "correction"), ("我怕我记错了", None), ("如果我没理解错的话", None), ("我们走错了方向", None),
])
def test_attention_keywords(tmp_path, text, kind):
    write_session(tmp_path, "eeeeeeee-0000", "Lead (R2V)", [user(text, origin="human")])
    [row] = run(tmp_path, "attention")
    assert (row["followup"], row["correction"]) == (int(kind == "followup"), int(kind == "correction"))


def test_attention_treats_a_markdown_brief_as_automated(tmp_path):
    write_session(tmp_path, "ffffffff-0000", "Lead (R2V)", [user("# 审核：新增开关\n\n## 背景", origin="human")])
    [row] = run(tmp_path, "attention")
    assert (row["user"], row["automated"]) == (0, 1)
