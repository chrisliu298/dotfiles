#!/usr/bin/env bash
# Claude Code status line — follows the terminal's light/dark ANSI palette
# Model · project · branch* · 9m
# ctx 26% 38k/200k · 5h 37% 2h41m · 7d 26% 4d3h · $1.45 · +141/-25

input=$(cat)

# ── Colors (terminal ANSI names; Ghostty supplies the OpenAI palette) ──
reset='\033[0m'
muted='\033[90m'
bold='\033[1m'
blue='\033[34m'                      # navigation: project, worktree
green='\033[32m'                     # branch, success, additions
red='\033[31m'                       # errors, deletions
cyan='\033[36m'                      # elapsed time
magenta='\033[35m'                   # context usage
yellow='\033[33m'                    # cost

# ── Extract fields (single jq call) ─────────────────────────────
eval "$(echo "$input" | jq -r '
  @sh "model=\(.model.display_name // "")",
  @sh "effort_level=\(.effort.level // "")",
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
  @sh "rl_5h=\(.rate_limits.five_hour.used_percentage // "")",
  @sh "rl_5h_reset=\(.rate_limits.five_hour.resets_at // "")",
  @sh "rl_7d=\(.rate_limits.seven_day.used_percentage // "")",
  @sh "rl_7d_reset=\(.rate_limits.seven_day.resets_at // "")"
')"

# ── Derived values ───────────────────────────────────────────────
# Project name (basename of project dir, or cwd abbreviated)
if [ -n "$project_dir" ]; then
  project="${project_dir##*/}"
else
  project="${cwd##*/}"
fi

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
    branch_segment="\033]8;;${remote_url}/tree/${clean_branch}\a${green}${branch}${reset}\033]8;;\a"
  else
    branch_segment="${green}${branch}${reset}"
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

# ── Shared helpers ────────────────────────────────────────────────
rl_reset_fmt() {
  local ts="$1"
  [ -z "$ts" ] && return
  local reset_epoch now_epoch diff_s
  if [[ "$ts" =~ ^[0-9]+$ ]]; then
    reset_epoch=$ts
  else
    reset_epoch=$(date -d "${ts%%.*}Z" +%s 2>/dev/null) \
      || reset_epoch=$(TZ=UTC date -jf "%Y-%m-%dT%H:%M:%S" "${ts%%.*}" +%s 2>/dev/null) \
      || return
  fi
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

# ── Build session and usage rows ──────────────────────────────────
parts=()
usage_parts=()

# Session info
if [ -n "$model" ]; then
  # Context size is shown in the ctx segment; drop the redundant suffix
  model_seg="${muted}${model% (1M context)}"
  [ -n "$effort_level" ] && model_seg+=" ${effort_level}"
  parts+=("${model_seg}${reset}")
fi
[ -n "$project" ] && parts+=("${blue}${project}${reset}")
[ -n "$branch_segment" ] && parts+=("$branch_segment")
[ -n "$wt_name" ] && parts+=("${blue}[${wt_name}]${reset}")
[ -n "$agent_name" ] && parts+=("${muted}${agent_name}${reset}")

if [ -n "$vim_mode" ]; then
  if [ "$vim_mode" = "NORMAL" ]; then
    parts+=("${green}${vim_mode}${reset}")
  else
    parts+=("${blue}${vim_mode}${reset}")
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
  [ "$total_s" -gt 0 ] && parts+=("${cyan}${dur}${reset}")
fi

# Rate limits (text only, no bars)
if [ -n "$rl_5h" ]; then
  rl5_pct="${rl_5h%.*}"
  rl5_seg="${muted}5h ${rl5_pct:-0}%${reset}"
  rl5_reset=$(rl_reset_fmt "$rl_5h_reset")
  [ -n "$rl5_reset" ] && rl5_seg+=" ${muted}${rl5_reset}${reset}"
  usage_parts+=("$rl5_seg")
fi

if [ -n "$rl_7d" ]; then
  rl7_pct="${rl_7d%.*}"
  rl7_seg="${muted}7d ${rl7_pct:-0}%${reset}"
  rl7_reset=$(rl_reset_fmt "$rl_7d_reset")
  [ -n "$rl7_reset" ] && rl7_seg+=" ${muted}${rl7_reset}${reset}"
  usage_parts+=("$rl7_seg")
fi

# Context window
pct="${used_pct%.*}"
pct="${pct:-0}"
(( pct > 100 )) && pct=100
(( pct < 0 )) && pct=0
ctx_seg="${muted}ctx ${magenta}${pct}%"
if [ -n "$cur_input" ] && [ -n "$ctx_size" ] && [ "$ctx_size" -gt 0 ]; then
  cur_tok=$(( ${cur_input:-0} + ${cur_output:-0} + ${cur_cache_create:-0} + ${cur_cache_read:-0} ))
  ctx_seg+="${muted} $(fmt_tokens "$cur_tok")/$(fmt_tokens "$ctx_size")"
fi
usage_parts=("${ctx_seg}${reset}" "${usage_parts[@]}")

# Cost
if [ -n "$cost" ] && [ "$cost" != "0" ]; then
  cost_fmt=$(printf "%.2f" "$cost")
  [ "$cost_fmt" != "0.00" ] && usage_parts+=("${yellow}\$${cost_fmt}${reset}")
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
  [ -n "$changes" ] && usage_parts+=("${changes}")
fi

# ── Output ────────────────────────────────────────────────────────
# NUL-delimited fields, with an empty field separating the two logical rows.
# Perl is included with macOS; Unicode::UCD keeps CJK and combining text aligned.
{
  [ "${#parts[@]}" -gt 0 ] && printf '%b\0' "${parts[@]}"
  printf '\0'
  printf '%b\0' "${usage_parts[@]}"
} | perl -CS -MUnicode::UCD=charprop -e '
  use strict;
  use warnings;
  use utf8;
  my $columns = $ENV{COLUMNS} // 120;
  $columns = 120 unless $columns =~ /\A[1-9][0-9]*\z/;
  # Leave room for Claude Code footer indentation and the terminal edge.
  my $width = $columns > 4 ? $columns - 4 : 1;
  my ($col, $style, $link) = (0, "", "");
  my %char_width;
  my $token = qr/\e\[[0-?]*[ -\/]*[\@-~]|\e\][^\a\e]*(?:\a|\e\\)|\X/;

  sub cell_width {
    my ($text) = @_;
    return 0 if $text =~ /\A\e/;
    my $cells = 0;
    for my $char (split //, $text) {
      next if $char =~ /[\p{Mn}\p{Me}\p{Cf}]/;
      my $n = ord $char;
      my $w = $char_width{$n} //= ($n < 128 ? 1 :
        charprop($n, "East_Asian_Width") =~ /\A(?:Wide|Fullwidth)\z/ ? 2 : 1);
      $cells = $w if $w > $cells;
    }
    return $cells;
  }

  sub new_row {
    print "\e]8;;\a" if length $link;
    print "\e[0m" if length $style;
    print "\n", $style, $link;
    $col = 0;
  }

  sub emit {
    my ($text) = @_;
    for my $piece ($text =~ /($token)/g) {
      my $cells = cell_width($piece);
      new_row() if $cells && $col && $col + $cells > $width;
      if ($piece =~ /\A\e\[[0-9;]*m\z/) {
        $style = "" if $piece eq "\e[0m" || $piece eq "\e[m";
        $style .= $piece unless $piece eq "\e[0m" || $piece eq "\e[m";
      } elsif ($piece =~ /\A\e\]8;[^;]*;(.*?)(?:\a|\e\\)\z/s) {
        $link = length($1) ? $piece : "";
      }
      print $piece;
      $col += $cells;
    }
  }

  local $/ = "\0";
  while (my $part = <STDIN>) {
    chomp $part;
    if (!length $part) {
      new_row() if $col;
      next;
    }
    my $cells = 0;
    $cells += cell_width($_) for $part =~ /($token)/g;
    new_row() if $col && $col + 3 + $cells > $width;
    emit("\e[90m · \e[0m") if $col;
    emit($part);
  }
'
