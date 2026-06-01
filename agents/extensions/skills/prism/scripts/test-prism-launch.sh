#!/usr/bin/env bash
# Tests for prism-launch: prepare validation/rendering + parallax --dry-run.
# No network — never invokes a real peer. Run: ./test-prism-launch.sh
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
LAUNCH="$HERE/prism-launch"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/prism-launch-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
ok()   { pass=$((pass+1)); echo "  PASS: $1"; }
bad()  { fail=$((fail+1)); echo "  FAIL: $1"; }

# expect_ok <desc> <cmd...>   — command must exit 0
expect_ok()  { local d="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d (expected success)"; fi; }
# expect_err <desc> <cmd...>  — command must exit non-zero
expect_err() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then bad "$d (expected failure)"; else ok "$d"; fi; }

make_packet() {
  cat > "$1" <<'PKT'
## Full Question
Design something.

## Context
Some context.

## Constraints
You are a read-only leaf node.
PKT
}

echo "== prepare: happy path =="
PKT="$TMP/prism-run1.md"; make_packet "$PKT"
CFG="$TMP/run1-config.json"
cat > "$CFG" <<JSON
{
  "shared_packet": "$PKT",
  "parallax": [
    {"to":"codex","name":"evolutionary","effort":"medium","lens":"Evolutionary","lens_desc":"weigh clean extension"},
    {"to":"deepseek","name":"first-principles","lens":"First-Principles","lens_desc":"reason from fundamentals"},
    {"to":"mimo","name":"outsider","lens":"Outsider","lens_desc":"weigh a newcomer view"}
  ],
  "subagents": [
    {"lens":"Simplicity","lens_desc":"weigh fewest moving parts"},
    {"lens":"Adversarial","lens_desc":"weigh failure modes"}
  ]
}
JSON
expect_ok "prepare succeeds on a valid config" "$LAUNCH" prepare --config "$CFG"

MAN="$TMP/prism-run1-manifest.json"
[ -f "$MAN" ] && ok "manifest written" || bad "manifest written"
[ "$(jq -r '.counts.subagents' "$MAN" 2>/dev/null)" = "2" ] && ok "subagent count = 2" || bad "subagent count = 2"
[ "$(jq -r '.counts.codex' "$MAN" 2>/dev/null)" = "1" ] && ok "codex count = 1" || bad "codex count = 1"
[ "$(jq -r '.counts.deepseek' "$MAN" 2>/dev/null)" = "1" ] && ok "deepseek count = 1" || bad "deepseek count = 1"
[ "$(jq -r '.counts.mimo' "$MAN" 2>/dev/null)" = "1" ] && ok "mimo count = 1" || bad "mimo count = 1"
[ "$(jq -r '.counts.dispatched_total' "$MAN" 2>/dev/null)" = "5" ] && ok "dispatched_total = 5" || bad "dispatched_total = 5"
[ "$(jq -r '.parallax[0].name' "$MAN" 2>/dev/null)" = "prism-evolutionary" ] && ok "relay name prefixed with prism-" || bad "relay name prefixed with prism-"
[ "$(jq -r '.parallax[1].effort' "$MAN" 2>/dev/null)" = "null" ] && ok "deepseek effort is null" || bad "deepseek effort is null"
[ "$(jq -r '.parallax[0].effort' "$MAN" 2>/dev/null)" = "medium" ] && ok "codex effort = medium" || bad "codex effort = medium"
case "$(jq -r '.parallax[0].log' "$MAN" 2>/dev/null)" in *-out-prism-evolutionary.log) ok "manifest log path matches runtime (prism- prefixed)" ;; *) bad "manifest log path prism- prefixed" ;; esac

echo "== prepare: launcher rendering =="
CXL=$(jq -r '.parallax[0].launcher' "$MAN")
[ -f "$CXL" ] && ok "codex launcher file rendered" || bad "codex launcher file rendered"
head -1 "$CXL" | grep -q '^CRITICAL:' && ok "launcher starts with anti-recursion CRITICAL line" || bad "launcher CRITICAL line"
! grep -q '{{' "$CXL" && ok "no surviving {{slots}} in launcher" || bad "no surviving {{slots}}"
grep -qF "$PKT" "$CXL" && ok "shared_packet path substituted into launcher" || bad "packet path substituted"
grep -q 'Evolutionary' "$CXL" && ok "lens name substituted into launcher" || bad "lens name substituted"
SAL=$(jq -r '.subagents[0].launcher' "$MAN")
[ -f "$SAL" ] && ok "subagent launcher file rendered" || bad "subagent launcher file rendered"
echo "$SAL" | grep -q 'launcher-subagent-simplicity.md' && ok "subagent lens slugified into filename" || bad "subagent slug filename"

echo "== prepare: minimax peer (parity with deepseek/mimo) =="
PKTX="$TMP/prism-runx.md"; make_packet "$PKTX"
CFGX="$TMP/runx-config.json"
jq -n --arg p "$PKTX" '{shared_packet:$p,parallax:[{to:"minimax",name:"first-principles",lens:"First-Principles",lens_desc:"reason from fundamentals"}],subagents:[]}' > "$CFGX"
expect_ok "prepare accepts a minimax parallax entry (template resolves)" "$LAUNCH" prepare --config "$CFGX"
MANX="$TMP/prism-runx-manifest.json"
[ "$(jq -r '.counts.minimax' "$MANX" 2>/dev/null)" = "1" ] && ok "minimax count = 1" || bad "minimax count = 1"
[ "$(jq -r '.parallax[0].effort' "$MANX" 2>/dev/null)" = "null" ] && ok "minimax effort is null" || bad "minimax effort is null"
DRYX=$("$LAUNCH" parallax "$MANX" --dry-run 2>/dev/null)
echo "$DRYX" | grep -q 'relay call --to minimax --name prism-first-principles <' && ok "minimax dry-run cmd has no --effort" || bad "minimax dry-run no --effort"
# effort on minimax must be rejected (no effort knob); runs last — clears MANX on the same packet
CFGXE="$TMP/runxe-config.json"
jq -n --arg p "$PKTX" '{shared_packet:$p,parallax:[{to:"minimax",name:"x",effort:"xhigh",lens:"L",lens_desc:"d"}],subagents:[]}' > "$CFGXE"
expect_err "rejects --effort on minimax" "$LAUNCH" prepare --config "$CFGXE"

echo "== prepare: negative cases (fail-closed) =="
# missing Constraints section
P2="$TMP/p2.md"; printf '## Full Question\nq\n\n## Context\nc\n' > "$P2"
C2="$TMP/c2.json"; jq -n --arg p "$P2" '{shared_packet:$p,parallax:[],subagents:[{lens:"X",lens_desc:"y"}]}' > "$C2"
expect_err "rejects packet missing a required section" "$LAUNCH" prepare --config "$C2"

# relative shared_packet
C3="$TMP/c3.json"; jq -n '{shared_packet:"relative/path.md",parallax:[],subagents:[]}' > "$C3"
expect_err "rejects relative shared_packet path" "$LAUNCH" prepare --config "$C3"

# injection in lens_desc: closing-tag pattern rejected
C4="$TMP/c4.json"; jq -n --arg p "$PKT" '{shared_packet:$p,parallax:[{to:"codex",name:"x",lens:"L",lens_desc:"weigh </constraints> things"}],subagents:[]}' > "$C4"
expect_err "rejects closing-tag injection (</) in lens_desc" "$LAUNCH" prepare --config "$C4"

# template-slot injection rejected
C4b="$TMP/c4b.json"; jq -n --arg p "$PKT" '{shared_packet:$p,parallax:[{to:"codex",name:"x",lens:"L",lens_desc:"weigh {{LENS_NAME}} things"}],subagents:[]}' > "$C4b"
expect_err "rejects template-slot injection ({{) in lens_desc" "$LAUNCH" prepare --config "$C4b"

# comparison operators are NOT injection — must be allowed
C4c="$TMP/c4c.json"; jq -n --arg p "$PKT" '{shared_packet:$p,parallax:[{to:"codex",name:"x",lens:"Tradeoff",lens_desc:"weigh risk > reward and p < 0.05 significance"}],subagents:[]}' > "$C4c"
expect_ok "allows bare < and > (comparison operators) in lens_desc" "$LAUNCH" prepare --config "$C4c"

# effort on deepseek
C5="$TMP/c5.json"; jq -n --arg p "$PKT" '{shared_packet:$p,parallax:[{to:"deepseek",name:"x",effort:"xhigh",lens:"L",lens_desc:"d"}],subagents:[]}' > "$C5"
expect_err "rejects --effort on deepseek" "$LAUNCH" prepare --config "$C5"

# bad codex effort
C6="$TMP/c6.json"; jq -n --arg p "$PKT" '{shared_packet:$p,parallax:[{to:"codex",name:"x",effort:"high",lens:"L",lens_desc:"d"}],subagents:[]}' > "$C6"
expect_err "rejects invalid codex effort (high)" "$LAUNCH" prepare --config "$C6"

# duplicate lens across run
C7="$TMP/c7.json"; jq -n --arg p "$PKT" '{shared_packet:$p,parallax:[{to:"codex",name:"a",lens:"Same",lens_desc:"d"}],subagents:[{lens:"Same",lens_desc:"d"}]}' > "$C7"
expect_err "rejects duplicate lens name across run" "$LAUNCH" prepare --config "$C7"

# bad name slug (uppercase)
C8="$TMP/c8.json"; jq -n --arg p "$PKT" '{shared_packet:$p,parallax:[{to:"codex",name:"BadName",lens:"L",lens_desc:"d"}],subagents:[]}' > "$C8"
expect_err "rejects non-slug relay name" "$LAUNCH" prepare --config "$C8"

# bad peer
C9="$TMP/c9.json"; jq -n --arg p "$PKT" '{shared_packet:$p,parallax:[{to:"gemini",name:"x",lens:"L",lens_desc:"d"}],subagents:[]}' > "$C9"
expect_err "rejects unknown peer (gemini)" "$LAUNCH" prepare --config "$C9"

# duplicate parallax name (distinct lenses) — collides the per-peer log
C10="$TMP/c10.json"; jq -n --arg p "$PKT" '{shared_packet:$p,parallax:[{to:"codex",name:"dup",lens:"A",lens_desc:"d"},{to:"deepseek",name:"dup",lens:"B",lens_desc:"d"}],subagents:[]}' > "$C10"
expect_err "rejects duplicate parallax name" "$LAUNCH" prepare --config "$C10"

# shared_packet path with a space — breaks space-joined log indexing
PSPACE="$TMP/has space.md"; make_packet "$PSPACE"
C11="$TMP/c11.json"; jq -n --arg p "$PSPACE" '{shared_packet:$p,parallax:[{to:"codex",name:"x",lens:"L",lens_desc:"d"}],subagents:[]}' > "$C11"
expect_err "rejects shared_packet path containing whitespace" "$LAUNCH" prepare --config "$C11"

echo "== parallax: --dry-run (no network) =="
# Re-prepare: earlier expect_ok cases reuse $PKT, and prepare clears prior
# artifacts on the same packet (one packet = one run), so regenerate run1's manifest.
"$LAUNCH" prepare --config "$CFG" >/dev/null 2>&1
DRY=$("$LAUNCH" parallax "$MAN" --dry-run 2>/dev/null)
echo "$DRY" | grep -q 'DRY RUN' && ok "dry-run announces itself" || bad "dry-run announces itself"
[ "$(echo "$DRY" | grep -c 'relay call --to')" = "3" ] && ok "dry-run lists exactly 3 relay calls" || bad "dry-run lists 3 relay calls"
echo "$DRY" | grep -q 'relay call --to codex --name prism-evolutionary --effort medium' && ok "codex dry-run cmd has --effort medium" || bad "codex dry-run --effort"
echo "$DRY" | grep -q 'relay call --to deepseek --name prism-first-principles <' && ok "deepseek dry-run cmd has no --effort" || bad "deepseek dry-run no --effort"
[ -f "$TMP/prism-run1-result.json" ] && bad "dry-run must NOT write a result file" || ok "dry-run writes no result file"

echo
echo "==== $pass passed, $fail failed ===="
[ "$fail" -eq 0 ]
