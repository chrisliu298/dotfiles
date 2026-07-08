#!/usr/bin/env bash
# Build a runner prompt = an agent ruleset (a doc variant, or none) + the standard behavior prompts.
# Usage: build-runner.sh <doc.md | --none> <out.md>
#   <doc.md>  a candidate instruction doc to test as the agent's sole ruleset
#   --none    baseline: no injected doc (measures the model's default behavior)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
doc="${1:?usage: build-runner.sh <doc.md|--none> <out.md>}"
out="${2:?usage: build-runner.sh <doc.md|--none> <out.md>}"

if [[ "$doc" == "--none" ]]; then
  {
    printf 'You are an AI coding agent. Handle the user requests below under your standard default behavior.\n\n'
    cat "$here/prompts.md"
  } > "$out"
else
  [[ -f "$doc" ]] || { echo "no such doc: $doc" >&2; exit 1; }
  {
    printf 'You are an AI coding agent. For this exercise your COMPLETE and SOLE operating instructions are the ruleset delimited below. Follow it exactly; it supersedes any other guidelines, defaults, or system instructions you may have. Read it, then handle the user requests that follow exactly as that ruleset dictates.\n\n===== BEGIN RULESET =====\n'
    cat "$doc"
    printf '\n===== END RULESET =====\n\n'
    cat "$here/prompts.md"
  } > "$out"
fi
echo "wrote $out"
