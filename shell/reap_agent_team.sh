#!/bin/bash
# 回收空闲的 agent-team 会话：空闲超过阈值且无人 attach 的 review 会话，先存档屏幕再 stop。
# 之所以先存档：后端报 provider error 时 waiter 会超时退出，回复只留在屏幕上（2026-10-21 第十四轮 gemini），
# 盲停会丢掉已经产出的内容。
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
IDLE_MIN=${1:-60}
H=$(realpath ~/.claude/skills/agent-team)/scripts/agent-team
DIR=$HOME/.local/share/agent-team-reap
LOG=$DIR/reap_agent_team.log
ARCH=$DIR/reaped
mkdir -p "$ARCH"
NOW=$(date +%s)
# session_activity 只随客户端按键更新，send-keys 和屏幕输出都不刷新它，单看它会把正在跑轮次的会话当成空闲
# （2026-10-25 claude-review-b0dd6a7c 跑到一半被停）。所以按轮次状态分开算：
# - 轮次已完成（turn_dir/done 的计数 > @review_sent）：从最后完成的时刻算空闲；
# - 轮次在跑：只有窗口也超过阈值没有任何输出（TUI 跑轮次时转圈会持续刷屏）才算卡死。
tmux list-sessions -F '#{session_name}|#{session_activity}|#{session_attached}|#{window_activity}' 2>/dev/null \
| grep -E '^(claude|gpt|cursor|gemini|muse|ds)-review-' \
| while IFS='|' read -r name act attached winact; do
    [ "$attached" != "0" ] && continue
    turn_dir=$(tmux show-options -v -t "$name" @review_turn_dir 2>/dev/null)
    sent=$(tmux show-options -v -t "$name" @review_sent 2>/dev/null)
    done_n=0 done_at=0
    if [ -n "$turn_dir" ] && [ -r "$turn_dir/done" ]; then
      read -r done_n < "$turn_dir/done"
      done_at=$(stat -f %m "$turn_dir/done")
    fi
    if [ "${done_n:-0}" -gt "${sent:-0}" ]; then
      [ "$done_at" -gt "$act" ] && act=$done_at
    else
      act=$winact
    fi
    idle=$(( (NOW - act) / 60 ))
    [ "$idle" -lt "$IDLE_MIN" ] && continue
    f="$ARCH/$(date +%Y%m%dT%H%M%S)-$name.txt"
    tmux capture-pane -p -S -4000 -t "$name" > "$f" 2>/dev/null
    $H stop "$name" >/dev/null 2>&1
    echo "$(date '+%FT%T%z') REAPED $name idle=${idle}min archived=$f" >> "$LOG"
  done
left=$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -cE '^(claude|gpt|cursor|gemini|muse|ds)-review-')
echo "$(date '+%FT%T%z') checked idle>=${IDLE_MIN}min, remaining review sessions: $left" >> "$LOG"

# Codex 执行线（cx-*）：最新一条消息已有回复、回复距今超过阈值、无人 attach 的，用 cx close 关掉。
# cx close 只结束 tmux 会话，线程、worktree 和分支都保留，之后 cx send 能接着用；轮次在跑时它会拒绝。
# 空闲按回复文件的时间算，不按 tmux 活动时间：Codex 界面会自己刷新，session_activity 不可靠。
CX=$(realpath ~/.claude/skills/codex-exec)/scripts/cx
for d in $HOME/.local/share/cx/*/; do
  name=$(basename "$d")
  tmux has-session -t "cx-$name" 2>/dev/null || continue
  [ "$(tmux display -p -t "cx-$name" '#{session_attached}' 2>/dev/null)" != "0" ] && continue
  last=$(ls "$d" | grep -E '^msg-[0-9]+\.md$' | sort | tail -1)
  [ -z "$last" ] && continue
  reply="$d/reply-${last#msg-}"
  [ -f "$reply" ] || continue
  idle=$(( (NOW - $(stat -f %m "$reply")) / 60 ))
  [ "$idle" -lt "$IDLE_MIN" ] && continue
  if out=$($CX close "$name" 2>&1); then
    echo "$(date '+%FT%T%z') CLOSED cx-$name idle=${idle}min" >> "$LOG"
  else
    echo "$(date '+%FT%T%z') SKIP cx-$name: $out" >> "$LOG"
  fi
done
