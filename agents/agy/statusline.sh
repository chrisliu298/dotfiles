#!/usr/bin/env bash
# Antigravity CLI (agy) status line, left-aligned in place of agy's built-in one (which sits at the
# right and cannot be moved): two logical rows matching Claude Code's status line
# (agents/claude/statusline-command.sh), each wrapped to the terminal width if needed:
#   auto · Gemini 4 Neon high · project · branch* · 2 tasks · 9m12s
#   ctx 14% 72.3k/512.0k · 5h 1% 4h47m · 7d 0% 6d23h
# ctx is measured against where agy compacts, not the model's 1M window, as the Claude line does with
# autoCompactWindow. agy has no setting for that point; it ships it per model (agy 1.5.12's built-in
# checkpointer profiles: 512K for every Gemini 4 model, 256K for Claude), so it is copied here and
# needs updating when agy changes it.
# The quota pair follows the active model: gemini-* buckets for Gemini models,
# 3p-* for third-party ones (Claude, GPT-OSS). Percentages are used, not remaining.
# agy runs this at most every 300 ms and kills it after 5 s; keep it to one jq call,
# zero subshell forks, and no bash-3.2 here-strings (which create /tmp files and stall
# behind macOS endpoint security). Field reference: antigravity.google/docs/cli/statusline.

reset='\033[0m'
muted='\033[90m'
blue='\033[34m'
green='\033[32m'
red='\033[31m'
cyan='\033[36m'
yellow='\033[33m'
magenta='\033[35m'

# No or broken input (agy's first call can come before the payload is complete, and agy #698 can
# hold stdin open without EOF under heavy turns): bound stdin wait to 1 s so agy never SIGKILLs
# the script at 5 s, and pass the JSON via --arg to avoid bash-3.2 here-string /tmp files.
IFS= read -r -d '' -t 1 input
[ -n "$input" ] || exit 0
fields=$(jq -nr --arg raw "$input" '
  ($raw | fromjson) |
  ((.model.display_name // "") | test("^(Claude|GPT)") | if . then "3p" else "gemini" end) as $q |
  ((.model.display_name // "") | if test("^Gemini 4 ") then 512000 elif test("^Claude") then 256000 else "" end) as $compact |
  @sh "compact_at=\($compact)",
  @sh "width=\(.terminal_width // 120)",
  @sh "cwd=\(.workspace.current_dir // .cwd // "")",
  @sh "project_dir=\(.workspace.project_dir // "")",
  @sh "used_pct=\(.context_window.used_percentage // 0 | floor)",
  @sh "ctx_size=\(.context_window.context_window_size // 0 | floor)",
  @sh "ctx_tok=\(if .context_window.current_usage then ((.context_window.used_percentage // 0) * (.context_window.context_window_size // 0) / 100 | floor) else "" end)",
  @sh "q5_used=\(.quota["\($q)-5h"].remaining_fraction | if . then (1 - .) * 100 | round else "" end)",
  @sh "q5_reset=\(.quota["\($q)-5h"].reset_in_seconds // "" | if . == "" then . else floor end)",
  @sh "q7_used=\(.quota["\($q)-weekly"].remaining_fraction | if . then (1 - .) * 100 | round else "" end)",
  @sh "q7_reset=\(.quota["\($q)-weekly"].reset_in_seconds // "" | if . == "" then . else floor end)",
  @sh "cost=\(.cost.total_usd // "")",
  @sh "agent_name=\(.agent.name // "")",
  @sh "state=\(.agent_state // "")",
  @sh "mode=\(.cycle_mode // "")",
  @sh "model=\(.model.display_name // "" | sub(" \\([^)]*\\)$"; ""))",
  @sh "effort=\(.model.effort // "")",
  @sh "vim_mode=\(.vim.mode // "")",
  @sh "vcs_type=\(.vcs.type // "")",
  @sh "sandbox=\(.sandbox.enabled // false)",
  @sh "confirm=\(.tool_confirmation_pending // false)",
  @sh "pending_input=\(.pending_input_count // 0 | floor)",
  @sh "transcript=\(.transcript_path // "")",
  @sh "now_epoch=\(now | floor)",
  @sh "tasks=\(.task_count // 0 | floor)",
  @sh "subagents=\([.subagents[]? | select(.status == "running")] | length)",
  @sh "tap_id=\(.conversation_id // "" | gsub("[^A-Za-z0-9-]"; ""))",
  @sh "tap_t=\(now | todate)",
  @sh "tap=\({conversation_id: (.conversation_id // ""), email: (.email // ""), plan_tier: (.plan_tier // ""),
              model: (.model.id // ""), quota: (.quota // {} | map_values(if type == "object" then del(.reset_in_seconds) else . end)),
              cost: (.cost // null)} | tojson)"
' 2>/dev/null) && [ -n "$fields" ] || exit 0
eval "$fields"

# Usage tap for gemini-usage-tracking, on only where its directory exists: agy's quota and each
# conversation's running cost reach no file, so every change is appended to events.jsonl
# (one line per change, the last one kept per conversation to compare against).
tap_dir="${AGY_USAGE_TAP:-$HOME/.local/state/agy-usage}"
if [ -d "$tap_dir/last" ]; then
  tap_last="$tap_dir/last/${tap_id:-none}"
  tap_old=""; [ -r "$tap_last" ] && IFS= read -r tap_old < "$tap_last"
  if [ "$tap_old" != "$tap" ]; then
    printf '%s\n' "$tap" >"$tap_last"
    printf '{"t":"%s",%s\n' "$tap_t" "${tap#\{}" >>"$tap_dir/events.jsonl"
  fi
fi

# Helpers assign out-variables instead of echoing to avoid subshell forks on every refresh.
fmt_tokens() {
  local n=$1
  if [ "$n" -ge 1000000 ]; then _tok="$((n / 1000000)).$(( (n % 1000000) / 100000 ))M"
  elif [ "$n" -ge 1000 ]; then _tok="$((n / 1000)).$(( (n % 1000) / 100 ))k"
  else _tok="$n"
  fi
}

fmt_secs() {
  local s=$1
  if [ "$s" -ge 86400 ]; then _sec="$((s / 86400))d$(( (s % 86400) / 3600 ))h"
  elif [ "$s" -ge 3600 ]; then _sec="$((s / 3600))h$(( (s % 3600) / 60 ))m"
  else _sec="$((s / 60))m"
  fi
}

usage_color() {
  if [ "$1" -ge 80 ]; then _col="$red"
  elif [ "$1" -ge 50 ]; then _col="$yellow"
  else _col="$green"
  fi
}

# Leave room for agy's footer margin so a near-full line is not clipped.
(( width > 4 )) && width=$(( width - 4 ))

# join <part>...: the parts separated by " · ", wrapped between parts to fit the terminal, as agy cuts a
# line that is too wide instead of wrapping it. Width counts characters with the color codes and
# OSC 8 links removed (a wide CJK character counts as one).
shopt -s extglob
join() {
  local out="" line=0 part plain n
  for part in "$@"; do
    plain=${part//\\033\]8;;*([!\\])\\a/}; plain=${plain//\\033\[*([0-9;])m/}; n=${#plain}
    if (( line == 0 )); then out+=$part line=$n
    elif (( line + 3 + n <= width )); then out+="${muted} · ${reset}${part}" line=$(( line + 3 + n ))
    else out+="\n${part}" line=$n
    fi
  done
  printf '%b\n' "$out"
}

# ── Session part ─────────────────────────────────────────────────
row1=()
[ -n "$mode" ] && row1+=("${yellow}${mode//\\/\\\\}${reset}")
if [ -n "$model" ]; then
  model_seg="${model//\\/\\\\}"
  [ -n "$effort" ] && model_seg+=" ${effort//\\/\\\\}"
  row1+=("$model_seg")
elif [ -n "$effort" ]; then
  row1+=("${effort//\\/\\\\}")
fi
repo_dir="${project_dir:-$cwd}"; repo_dir="${repo_dir/#\~/$HOME}"
[ "$repo_dir" != / ] && repo_dir="${repo_dir%/}"
project="${repo_dir##*/}"
[ -n "$project" ] && row1+=("${blue}${project//\\/\\\\}${reset}")

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/agy-statusline"
if [ "$vcs_type" = git ] && [ -n "$repo_dir" ]; then
  repo_key="${repo_dir//[^A-Za-z0-9._-]/_}"
  git_cache="$cache_dir/git-${repo_key}"
  branch="" dirty="" remote_url="" cache_ts=""
  had_cache=0
  if [ -r "$git_cache" ]; then
    had_cache=1
    { IFS= read -r cache_ts; IFS= read -r branch; IFS= read -r dirty; IFS= read -r remote_url; } < "$git_cache"
  fi
  if ! [[ "$cache_ts" =~ ^[0-9]+$ ]] || (( now_epoch - cache_ts >= 15 )); then
    to_cmd=()
    if command -v timeout >/dev/null 2>&1; then to_cmd=(timeout 1)
    elif command -v gtimeout >/dev/null 2>&1; then to_cmd=(gtimeout 1)
    elif [ -x /opt/homebrew/bin/gtimeout ]; then to_cmd=(/opt/homebrew/bin/gtimeout 1)
    fi
    # Always pass -uno: untracked directory traversal hits macOS endpoint-security readdir stalls
    # and can exceed agy's 5 s SIGKILL limit on large repos.
    git_status=$("${to_cmd[@]}" git -C "$repo_dir" --no-optional-locks status --porcelain=v2 --branch -uno 2>/dev/null)
    git_rc=$?
    if [ "$git_rc" -eq 0 ]; then
      branch="" dirty=""
      _rest="${git_status}"$'\n'
      while [ -n "$_rest" ]; do
        line="${_rest%%$'\n'*}"
        _rest="${_rest#*$'\n'}"
        case "$line" in
          "# branch.head "*) branch="${line#\# branch.head }" ;;
          "#"*|"") ;;
          *) dirty="*"; break ;;
        esac
      done
      [ "$branch" = "(detached)" ] && branch=$("${to_cmd[@]}" git -C "$repo_dir" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
      # Resolve origin URL once per repo cache; it rarely changes and avoids an extra git spawn.
      if [ "$had_cache" -eq 0 ] && [ -n "$branch" ]; then
        remote_url=$("${to_cmd[@]}" git -C "$repo_dir" --no-optional-locks remote get-url origin 2>/dev/null)
        remote_url="${remote_url/git@github.com:/https://github.com/}"; remote_url="${remote_url%.git}"
      fi
    fi
    # Always update cache_ts (even on timeout) so a stalled git backs off for 15 s instead of retrying every 300 ms.
    if [ -d "$cache_dir" ] || mkdir -p "$cache_dir" 2>/dev/null; then
      tmp_cache="${git_cache}.$$"
      printf '%s\n%s\n%s\n%s\n' "$now_epoch" "$branch" "$dirty" "$remote_url" > "$tmp_cache" && mv "$tmp_cache" "$git_cache"
    fi
  fi
  if [ -n "$branch" ]; then
    branch_lit="${branch//\\/\\\\}"
    if [[ "$remote_url" == https://* ]]; then
      url_lit="${remote_url//\\/\\\\}/tree/${branch_lit}"
      row1+=("\033]8;;${url_lit}\a${green}${branch_lit}${dirty}${reset}\033]8;;\a")
    else
      row1+=("${green}${branch_lit}${dirty}${reset}")
    fi
  fi
fi

[ -n "$agent_name" ] && row1+=("${muted}${agent_name//\\/\\\\}${reset}")
[ -n "$vim_mode" ] && row1+=("${blue}${vim_mode}${reset}")
[ "$sandbox" = true ] && row1+=("${muted}sandbox${reset}")
[ "$confirm" = true ] && row1+=("${yellow}confirm${reset}")
[ "$state" = error ] && row1+=("${red}error${reset}")
[ "$pending_input" -gt 0 ] && row1+=("${yellow}${pending_input} queued${reset}")
if [ "$subagents" -gt 0 ]; then
  (( subagents > 1 )) && _pl=s || _pl=""
  row1+=("${muted}${subagents} subagent${_pl}${reset}")
fi
if [ "$tasks" -gt 0 ]; then
  (( tasks > 1 )) && _pl=s || _pl=""
  row1+=("${muted}${tasks} task${_pl}${reset}")
fi

# Session duration from transcript birth time (agy has no duration field; fall back to the
# standard antigravity-cli brain path when transcript_path is empty or points elsewhere).
transcript="${transcript/#\~/$HOME}"
if [ ! -f "$transcript" ] && [ -n "$tap_id" ]; then
  transcript="$HOME/.gemini/antigravity-cli/brain/$tap_id/.system_generated/logs/transcript.jsonl"
fi
birth=""
if [ -n "$tap_id" ]; then
  birth_cache="$cache_dir/birth-${tap_id}"
  [ -r "$birth_cache" ] && IFS= read -r birth < "$birth_cache"
fi
if ! [[ "$birth" =~ ^[1-9][0-9]*$ ]] && [ -n "$transcript" ] && [ -f "$transcript" ]; then
  if [[ "$OSTYPE" == darwin* ]]; then
    birth=$(/usr/bin/stat -f %B "$transcript" 2>/dev/null)
  else
    birth=$(stat -c %W "$transcript" 2>/dev/null)
  fi
  if [[ "$birth" =~ ^[1-9][0-9]*$ ]] && [ -n "${birth_cache:-}" ]; then
    if [ -d "$cache_dir" ] || mkdir -p "$cache_dir" 2>/dev/null; then
      printf '%s\n' "$birth" > "${birth_cache}.$$" && mv "${birth_cache}.$$" "$birth_cache"
    fi
  fi
fi
if [[ "$birth" =~ ^[1-9][0-9]*$ ]] && (( now_epoch > birth )); then
  total_s=$(( now_epoch - birth ))
  if [ "$total_s" -ge 3600 ]; then
    dur="$((total_s / 3600))h$(( (total_s % 3600) / 60 ))m"
  elif [ "$total_s" -ge 60 ]; then
    dur="$((total_s / 60))m$((total_s % 60))s"
  else
    dur="${total_s}s"
  fi
  row1+=("${cyan}${dur}${reset}")
fi

# ── Usage part ───────────────────────────────────────────────────
row2=()
pct="${used_pct%.*}"; pct="${pct:-0}"
usage_color "$pct"
ctx_seg="${muted}ctx ${_col}${pct}%"
if [ -n "$ctx_tok" ] && [ "$ctx_size" -gt 0 ]; then
  if [ -n "$compact_at" ] && [ "$compact_at" -lt "$ctx_size" ]; then
    ctx_size=$compact_at pct=$(( ctx_tok * 100 / compact_at ))
    usage_color "$pct"
    ctx_seg="${muted}ctx ${_col}${pct}%"
  fi
  fmt_tokens "$ctx_tok"; _tok_used="$_tok"
  fmt_tokens "$ctx_size"; _tok_max="$_tok"
  ctx_seg+=" ${magenta}${_tok_used}${muted}/${_tok_max}"
fi
row2+=("${ctx_seg}${reset}")

quota_seg() {
  local label=$1 used=$2 secs=$3
  [ -n "$used" ] || return
  usage_color "$used"
  local seg="${muted}${label} ${_col}${used}%${reset}"
  if [ -n "$secs" ] && [ "$secs" -gt 0 ]; then
    fmt_secs "$secs"
    seg+=" ${muted}${_sec}${reset}"
  fi
  row2+=("$seg")
}
quota_seg 5h "$q5_used" "$q5_reset"
quota_seg 7d "$q7_used" "$q7_reset"

if [ -n "$cost" ]; then
  printf -v cost_fmt '%.2f' "$cost"
  [ "$cost_fmt" != "0.00" ] && row2+=("${yellow}\$${cost_fmt}${reset}")
fi

[ "${#row1[@]}" -gt 0 ] && join "${row1[@]}"
[ "${#row2[@]}" -gt 0 ] && join "${row2[@]}"
