#!/usr/bin/env bash
# Fan a runner prompt out to the cross-model relay peers and collect cleaned answers.
# Usage: run-peers.sh <runner.md> <label> [outdir]
# Requires the `relay` skill on PATH. Claude and gpt-pro are NOT included here:
#   - Claude: dispatch the runner via a Claude subagent (Agent tool), not relay.
#   - gpt-pro: excluded by design (slow, quota-burning).
set -euo pipefail
runner="${1:?usage: run-peers.sh <runner.md> <label> [outdir]}"
label="${2:?usage: run-peers.sh <runner.md> <label> [outdir]}"
outdir="${3:-.}"
mkdir -p "$outdir"

# peer:effort  (empty effort => no --effort flag; scales are vendor-specific)
peers=( "gpt:xhigh" "grok-build:high" "glm:" "kimi:" "deepseek:" "mimo:" )
for pe in "${peers[@]}"; do
  peer="${pe%%:*}"; eff="${pe##*:}"
  args=( --to "$peer" --name "eval-$label-$peer" )
  [[ -n "$eff" ]] && args+=( --effort "$eff" )
  echo "dispatching $peer ..."
  if relay call "${args[@]}" < "$runner" > "$outdir/out_${label}_${peer}.res.md" 2> "$outdir/out_${label}_${peer}.log"; then
    # strip relay YAML frontmatter -> clean numbered answers for the judge
    awk 'BEGIN{n=0} /^---$/{n++; next} n>=2{print}' "$outdir/out_${label}_${peer}.res.md" > "$outdir/clean_${label}_${peer}.md"
  else
    echo "  $peer FAILED (see $outdir/out_${label}_${peer}.log)"
  fi
done
echo "done -> $outdir"
