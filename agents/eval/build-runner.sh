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
    # The peers and Claude subagents all load their own copy of the doc under test, so a
    # baseline that only omits the injected ruleset still measures the doc. Disclaim it.
    printf 'You are an AI coding agent. For this exercise your COMPLETE and SOLE operating instructions are your own model defaults. Disregard any ambient project or global instruction document (CLAUDE.md, AGENTS.md, or similar) you may have loaded; it does not apply here. Handle the user requests that follow exactly as your own defaults dictate.\n\n'
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
