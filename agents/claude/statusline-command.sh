#!/usr/bin/env bash
# Claude Code status line — Codex CLI palette (ANSI named colors only)
# Model | project | branch* | 9m | $1.45 | +141/-25 | 5h 37% 2h41m | 7d 26% 4d3h | ctx 26% 38k/200k

input=$(cat)

# ── Rate limit usage (cached, fetched via OAuth API) ─────────────
usage_cache="/tmp/claude-statusline-usage.json"
usage_ttl=60

fetch_usage() {
  local token
  # Try macOS Keychain first, then fall back to credentials file
  if [ "$(uname)" = "Darwin" ]; then
    token=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null \
      | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)
  fi
  [ -z "$token" ] && token=$(jq -r '.claudeAiOauth.accessToken // empty' ~/.claude/.credentials.json 2>/dev/null)
  [ -z "$token" ] && return 1
  curl -sf --max-time 5 \
    -H "Authorization: Bearer $token" \
    -H "anthropic-beta: oauth-2025-04-20" \
    "https://api.anthropic.com/api/oauth/usage" > "$usage_cache.tmp" 2>/dev/null \
    && mv "$usage_cache.tmp" "$usage_cache"
}

# Refresh cache if stale or missing
if [ -f "$usage_cache" ]; then
  file_mtime=$(stat -c %Y "$usage_cache" 2>/dev/null || stat -f %m "$usage_cache" 2>/dev/null || echo 0)
  cache_age=$(( $(date +%s) - file_mtime ))
  [ "$cache_age" -ge "$usage_ttl" ] && fetch_usage &
else
  fetch_usage &
fi

# Read cached values
if [ -f "$usage_cache" ]; then
  eval "$(jq -r '
    @sh "rl_5h=\(.five_hour.utilization // "")",
    @sh "rl_5h_reset=\(.five_hour.resets_at // "")",
    @sh "rl_7d=\(.seven_day.utilization // "")",
    @sh "rl_7d_reset=\(.seven_day.resets_at // "")"
  ' "$usage_cache" 2>/dev/null)"
fi

# ── Colors (Codex CLI — ANSI named colors only) ───────────────────
reset='\033[0m'
dim='\033[2m'
bold='\033[1m'
cyan='\033[36m'                      # branding: project, worktree
magenta='\033[35m'                   # accent: branch, links
green='\033[32m'                     # success, additions
red='\033[31m'                       # errors, deletions

# ── Extract fields (single jq call) ─────────────────────────────
eval "$(echo "$input" | jq -r '
  @sh "model=\(.model.display_name // "")",
  @sh "cwd=\(.workspace.current_dir // .cwd // "")",
  @sh "project_dir=\(.workspace.project_dir // "")",
  @sh "used_pct=\(.context_window.used_percentage // "")",
  @sh "ctx_size=\(.context_window.context_window_size // "")",
  @sh "cur_input=\(.context_window.current_usage.input_tokens // "")",
  @sh "cur_output=\(.context_window.current_usage.output_tokens // "")",
  @sh "cur_cache_create=\(.context_window.current_usage.cache_creation_input_tokens // "")",
  @sh "cur_cache_read=\(.context_window.current_usage.cache_read_input_tokens // "")",
  @sh "cost=\(.cost.total_cost_usd // "")",
  @sh "duration_ms=\(.cost.total_duration_ms // "")",
  @sh "lines_add=\(.cost.total_lines_added // "")",
  @sh "lines_rm=\(.cost.total_lines_removed // "")",
  @sh "wt_name=\(.worktree.name // "")",
  @sh "wt_branch=\(.worktree.branch // "")",
  @sh "agent_name=\(.agent.name // "")",
  @sh "vim_mode=\(.vim.mode // "")",
  @sh "session_name=\(.session_name // "")"
')"

# ── Derived values ───────────────────────────────────────────────
# Project name (basename of project dir, or cwd abbreviated)
if [ -n "$project_dir" ]; then
  project="${project_dir##*/}"
else
  project="${cwd##*/}"
fi

# Append session name when set via /rename
[ -n "$session_name" ] && project="${project} > ${session_name}"

# Git branch — use worktree.branch if available, else detect
dir_expanded="${cwd/#\~/$HOME}"
if [ -n "$wt_branch" ]; then
  branch="$wt_branch"
elif git -C "${project_dir:-$dir_expanded}" --no-optional-locks rev-parse --is-inside-work-tree &>/dev/null; then
  branch=$(git -C "${project_dir:-$dir_expanded}" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
           || git -C "${project_dir:-$dir_expanded}" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
  # Dirty indicator
  if [ -n "$(git -C "${project_dir:-$dir_expanded}" --no-optional-locks status --porcelain 2>/dev/null | head -1)" ]; then
    branch+="*"
  fi
fi

# OSC 8 clickable branch → GitHub
branch_segment=""
if [ -n "$branch" ]; then
  remote_url=$(git -C "${project_dir:-$dir_expanded}" --no-optional-locks remote get-url origin 2>/dev/null \
    | sed 's|git@github.com:|https://github.com/|' | sed 's|\.git$||')
  if [ -n "$remote_url" ]; then
    clean_branch="${branch%\*}"
    branch_segment="\033]8;;${remote_url}/tree/${clean_branch}\a${magenta}${branch}${reset}\033]8;;\a"
  else
    branch_segment="${magenta}${branch}${reset}"
  fi
fi

# ── Helpers ──────────────────────────────────────────────────────
# Format large numbers compactly (pure bash, no awk)
fmt_tokens() {
  local n=$1
  if [ "$n" -ge 1000000 ]; then
    local whole=$((n / 1000000)) frac=$(( (n % 1000000) / 100000 ))
    echo "${whole}.${frac}M"
  elif [ "$n" -ge 1000 ]; then
    local whole=$((n / 1000)) frac=$(( (n % 1000) / 100 ))
    echo "${whole}.${frac}k"
  else
    echo "$n"
  fi
}

join_parts() {
  local sep="$1"; shift
  local out=""
  for p in "$@"; do
    [ -n "$out" ] && out+="$sep"
    out+="$p"
  done
  printf '%s' "$out"
}

# Strip ANSI escape sequences to measure visible width
# Handles: CSI (\e[...X), OSC (\e]...BEL/ST), stray ESC sequences
strip_ansi() {
  local str
  str=$(printf '%b' "$1")
  printf '%s' "$str" | sed \
    -e $'s/\033][^\a]*\a//g' \
    -e $'s/\033][^\033]*\033\\\\//g' \
    -e $'s/\033\\[[0-9;]*[A-Za-z]//g'
}

visible_len() {
  local stripped
  stripped=$(strip_ansi "$1")
  echo ${#stripped}
}

# ── Shared helpers ────────────────────────────────────────────────
rl_reset_fmt() {
  local ts="$1"
  [ -z "$ts" ] && return
  local reset_epoch now_epoch diff_s
  reset_epoch=$(date -d "${ts%%.*}Z" +%s 2>/dev/null) \
    || reset_epoch=$(TZ=UTC date -jf "%Y-%m-%dT%H:%M:%S" "${ts%%.*}" +%s 2>/dev/null) \
    || return
  now_epoch=$(date +%s)
  diff_s=$((reset_epoch - now_epoch))
  [ "$diff_s" -le 0 ] && { echo "now"; return; }
  if [ "$diff_s" -ge 86400 ]; then
    local d=$((diff_s / 86400)) h=$(( (diff_s % 86400) / 3600 ))
    echo "${d}d${h}h"
  elif [ "$diff_s" -ge 3600 ]; then
    local h=$((diff_s / 3600)) m=$(( (diff_s % 3600) / 60 ))
    echo "${h}h${m}m"
  else
    local m=$((diff_s / 60))
    echo "${m}m"
  fi
}

# ── Build single-line output ──────────────────────────────────────
sep="${dim} | ${reset}"
parts=()

# Session info
[ -n "$model" ] && parts+=("${dim}${model}${reset}")
[ -n "$project" ] && parts+=("${cyan}${project}${reset}")
[ -n "$branch_segment" ] && parts+=("$branch_segment")
[ -n "$wt_name" ] && parts+=("${cyan}[${wt_name}]${reset}")
[ -n "$agent_name" ] && parts+=("${dim}${agent_name}${reset}")

if [ -n "$vim_mode" ]; then
  if [ "$vim_mode" = "NORMAL" ]; then
    parts+=("${green}${vim_mode}${reset}")
  else
    parts+=("${cyan}${vim_mode}${reset}")
  fi
fi

# Duration
if [ -n "$duration_ms" ] && [ "$duration_ms" != "0" ]; then
  total_s=$((${duration_ms%.*} / 1000))
  if [ "$total_s" -ge 3600 ]; then
    h=$((total_s / 3600)); m=$(( (total_s % 3600) / 60 ))
    dur="${h}h${m}m"
  elif [ "$total_s" -ge 60 ]; then
    m=$((total_s / 60)); s=$((total_s % 60))
    dur="${m}m${s}s"
  else
    dur="${total_s}s"
  fi
  [ "$total_s" -gt 0 ] && parts+=("${dim}${dur}${reset}")
fi

# Rate limits (text only, no bars)
if [ -n "$rl_5h" ]; then
  rl5_pct="${rl_5h%.*}"
  rl5_seg="${dim}5h ${rl5_pct:-0}%${reset}"
  rl5_reset=$(rl_reset_fmt "$rl_5h_reset")
  [ -n "$rl5_reset" ] && rl5_seg+=" ${dim}${rl5_reset}${reset}"
  parts+=("$rl5_seg")
fi

if [ -n "$rl_7d" ]; then
  rl7_pct="${rl_7d%.*}"
  rl7_seg="${dim}7d ${rl7_pct:-0}%${reset}"
  rl7_reset=$(rl_reset_fmt "$rl_7d_reset")
  [ -n "$rl7_reset" ] && rl7_seg+=" ${dim}${rl7_reset}${reset}"
  parts+=("$rl7_seg")
fi

# Context window
pct="${used_pct%.*}"
pct="${pct:-0}"
(( pct > 100 )) && pct=100
(( pct < 0 )) && pct=0
ctx_seg="${dim}ctx ${pct}%"
if [ -n "$cur_input" ] && [ -n "$ctx_size" ] && [ "$ctx_size" -gt 0 ]; then
  cur_tok=$(( ${cur_input:-0} + ${cur_output:-0} + ${cur_cache_create:-0} + ${cur_cache_read:-0} ))
  ctx_seg+=" $(fmt_tokens "$cur_tok")/$(fmt_tokens "$ctx_size")"
fi
parts+=("${ctx_seg}${reset}")

# Cost
if [ -n "$cost" ] && [ "$cost" != "0" ]; then
  cost_fmt=$(printf "%.2f" "$cost")
  [ "$cost_fmt" != "0.00" ] && parts+=("${dim}\$${cost_fmt}${reset}")
fi

# Lines changed
if [ -n "$lines_add" ] || [ -n "$lines_rm" ]; then
  la=${lines_add:-0}; lr=${lines_rm:-0}
  changes=""
  [ "$la" != "0" ] && changes="${green}+${la}${reset}"
  [ "$lr" != "0" ] && {
    [ -n "$changes" ] && changes+="/"
    changes+="${red}-${lr}${reset}"
  }
  [ -n "$changes" ] && parts+=("${changes}")
fi

# ── Output (wrap to 2 lines if over 130 visible chars) ───────────
max_width=110
sep_vis=3  # visible width of " | "

# Single pass: compute total visible width and find split point
split=${#parts[@]}
line1_vis=0
total_vis=0
for i in "${!parts[@]}"; do
  plen=$(visible_len "${parts[$i]}")
  if [ "$i" -eq 0 ]; then
    total_vis=$plen
    cand=$plen
  else
    total_vis=$((total_vis + sep_vis + plen))
    cand=$((line1_vis + sep_vis + plen))
  fi
  if [ "$split" -eq "${#parts[@]}" ] && [ "$cand" -gt "$max_width" ]; then
    split=$i
  else
    line1_vis=$cand
  fi
done

if [ "$total_vis" -le "$max_width" ]; then
  printf '%b' "$(join_parts "$sep" "${parts[@]}")"
else
  [ "$split" -eq 0 ] && split=1
  printf '%b\n%b' "$(join_parts "$sep" "${parts[@]:0:$split}")" "$(join_parts "$sep" "${parts[@]:$split}")"
fi
