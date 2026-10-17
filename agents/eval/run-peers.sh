#!/usr/bin/env bash
# Send a runner prompt to the cross-model peer(s) through agent-team and collect their answers.
# Usage: run-peers.sh <runner.md> <label> [outdir]
# Requires the agent-team skill (installed for Claude). Claude and gpt-pro are NOT included here:
#   - Claude: dispatch the runner via a Claude subagent (Agent tool).
#   - gpt-pro: excluded by design (slow, quota-burning).
set -euo pipefail
runner="${1:?usage: run-peers.sh <runner.md> <label> [outdir]}"
label="${2:?usage: run-peers.sh <runner.md> <label> [outdir]}"
outdir="${3:-.}"
mkdir -p "$outdir"
helper="$HOME/.claude/skills/agent-team/scripts/agent-team"

peers=( gpt )
for peer in "${peers[@]}"; do
  echo "dispatching $peer ..."
  if ! "$helper" --once --backend "$peer" < "$runner" > "$outdir/clean_${label}_${peer}.md" 2> "$outdir/out_${label}_${peer}.log"; then
    echo "  $peer FAILED (see $outdir/out_${label}_${peer}.log)"
  fi
done
echo "done -> $outdir"
