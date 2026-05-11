#!/usr/bin/env bash
# Compile every example in the typst skill's examples/ directory.
# Run after editing SKILL.md, references/*, or examples/ to catch regressions.
#
# Usage: ./scripts/check-examples.sh

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXAMPLES_DIR="$SKILL_DIR/examples"
OUT_DIR="$(mktemp -d -t typst-skill-check-XXXXXX)"

if ! command -v typst >/dev/null 2>&1; then
  echo "typst not found in PATH" >&2
  exit 1
fi

echo "typst: $(typst --version)"
echo "examples: $EXAMPLES_DIR"
echo "output:   $OUT_DIR"
echo

failed=()
for typ in "$EXAMPLES_DIR"/*.typ; do
  name="$(basename "$typ" .typ)"
  printf '  %-20s ' "$name"
  if typst compile --root "$SKILL_DIR" "$typ" "$OUT_DIR/$name.pdf" 2>"$OUT_DIR/$name.err"; then
    echo "ok"
  else
    echo "FAIL"
    failed+=("$name")
    sed 's/^/      /' "$OUT_DIR/$name.err"
  fi
done

echo
if (( ${#failed[@]} > 0 )); then
  echo "Failures: ${failed[*]}" >&2
  exit 1
fi
echo "All examples compiled cleanly."
