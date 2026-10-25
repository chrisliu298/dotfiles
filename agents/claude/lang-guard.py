#!/usr/bin/env python3
"""Keep user-facing replies in Simplified Chinese (the language rule in agents/AGENTS.md).

  lang-guard stop        Stop hook: an English final reply is blocked once and rewritten in Chinese
  lang-guard post-tool   PostToolUse hook: English narration before a tool call adds a reminder to the context
  lang-guard check       read text on stdin, print whether it counts as English

The rule sits at the top of the system prompt while long sessions fill up with English thinking and tool
output, so replies drift into English and each English reply makes the next one likelier. A reminder at the
end of the context breaks that chain. Only interactive sessions are checked: `claude -p` output feeds scripts,
and agent-team reviewers (CODEX_REVIEW_SUBAGENT_ACTIVE=1) report to the lead, not the user.
"""
import json, os, re, sys

CODE = re.compile(r"```.*?```|`[^`\n]*`|https?://\S+", re.S)
CJK = re.compile(r"[一-鿿]")
WORD = re.compile(r"[A-Za-z]+(?:'[a-z]+)?")
STOPWORDS = {"a", "an", "the", "and", "but", "or", "so", "as", "is", "are", "was", "be", "to", "of", "in", "on", "for",
             "from", "with", "it", "its", "that", "this", "they", "their", "i", "i'm", "i'll", "my", "not", "now", "next",
             "then", "also", "still", "than"}


def is_english(text):
    """Prose with almost no CJK. Code, inline code and URLs don't count; an identifier dump without English
    function words is not prose."""
    text = CODE.sub(" ", text)
    words = WORD.findall(text)
    cjk = len(CJK.findall(text))
    if sum(map(len, words)) + cjk < 30:
        return False
    return cjk < 0.25 * len(words) and sum(w.lower() in STOPWORDS for w in words) >= 2


def tail_records(path, size=2_000_000):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - size))
            return f.read().decode("utf-8", "ignore").splitlines()[1:]
    except OSError:
        return []


def narration(path, tool_use_id):
    """Text the assistant wrote in the message that issued this tool call, or None unless the call is the
    message's first tool_use (parallel calls would repeat the reminder)."""
    lines = tail_records(path)
    msg_id = None
    for line in reversed(lines):
        if tool_use_id in line:
            r = json.loads(line)
            if r.get("type") == "assistant":
                msg_id = r["message"]["id"]
                break
    if msg_id is None:
        return None
    blocks = [b for line in lines if msg_id in line
              for r in [json.loads(line)] if r.get("type") == "assistant" and r["message"].get("id") == msg_id
              for b in r["message"].get("content") or [] if isinstance(b, dict)]
    first = next((b for b in blocks if b.get("type") == "tool_use"), None)
    if first is None or first.get("id") != tool_use_id:
        return None
    return "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def main(cmd):
    if cmd == "check":
        print("english" if is_english(sys.stdin.read()) else "ok")
        return
    event = json.load(sys.stdin)
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT") != "cli" or os.environ.get("CODEX_REVIEW_SUBAGENT_ACTIVE") == "1":
        return
    if cmd == "stop":
        text = str(event.get("last_assistant_message") or "")
        if event.get("stop_hook_active") or text.startswith("API Error") or not is_english(text):
            return
        print(json.dumps({"decision": "block", "reason": (
            "[lang-guard] 刚才这条回复是英文。面向用户的文字一律用简体中文：把这条回复用简体中文完整重写一遍"
            "（代码、命令、标识符、路径、报错原文保持原样）。直接给出中文版，不要解释为什么重写，也不要重复执行任何操作。")}, ensure_ascii=False))
    elif cmd == "post-tool":
        text = narration(event.get("transcript_path", ""), event.get("tool_use_id") or "\0")
        if text and is_english(text):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": (
                "[lang-guard] 上一段说明是英文。之后所有面向用户的文字（包括工具调用之间的简短说明和最终汇报）"
                "一律用简体中文。")}}, ensure_ascii=False))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    try:
        main(sys.argv[1] if sys.argv[1:] else "")
    except Exception as e:  # a broken hook must never block a session
        print(f"[lang-guard] hook error: {e}", file=sys.stderr)
        sys.exit(0)
