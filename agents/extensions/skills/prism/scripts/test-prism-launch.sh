#!/usr/bin/env bash
# Tests for prism-launch: prepare validation/rendering + parallax --dry-run.
# No network — never invokes a real peer. Run: ./test-prism-launch.sh
# Unset RELAY_PEER so the suite runs even when invoked from inside a relay peer
# subprocess (otherwise prism-launch's anti-recursion guard refuses every call and
# the whole suite fails — a harness artifact, not a regression).
unset RELAY_PEER
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
    {"to":"codex","name":"temporal","effort":"medium","lens":"Temporal","lens_desc":"weigh clean extension"},
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
[ "$(jq -r '.counts.by_peer.codex' "$MAN" 2>/dev/null)" = "1" ] && ok "codex count = 1" || bad "codex count = 1"
[ "$(jq -r '.counts.by_peer.deepseek' "$MAN" 2>/dev/null)" = "1" ] && ok "deepseek count = 1" || bad "deepseek count = 1"
[ "$(jq -r '.counts.by_peer.mimo' "$MAN" 2>/dev/null)" = "1" ] && ok "mimo count = 1" || bad "mimo count = 1"
[ "$(jq -r '.counts.dispatched_total' "$MAN" 2>/dev/null)" = "5" ] && ok "dispatched_total = 5" || bad "dispatched_total = 5"
[ "$(jq -r '.parallax[0].name' "$MAN" 2>/dev/null)" = "prism-temporal" ] && ok "relay name prefixed with prism-" || bad "relay name prefixed with prism-"
[ "$(jq -r '.parallax[1].effort' "$MAN" 2>/dev/null)" = "null" ] && ok "deepseek effort is null" || bad "deepseek effort is null"
[ "$(jq -r '.parallax[0].effort' "$MAN" 2>/dev/null)" = "xhigh" ] && ok "codex effort derived xhigh (authored 'medium' in --config ignored)" || bad "codex effort derived xhigh"
[ "$(jq -r '.parallax[0].template' "$MAN" 2>/dev/null)" = "codex" ] && ok "codex uses codex template (registry)" || bad "codex template = codex"
[ "$(jq -r '.parallax[1].template' "$MAN" 2>/dev/null)" = "costar" ] && ok "deepseek uses shared costar template (registry)" || bad "deepseek template = costar"
case "$(jq -r '.parallax[0].log' "$MAN" 2>/dev/null)" in *-out-prism-temporal.log) ok "manifest log path matches runtime (prism- prefixed)" ;; *) bad "manifest log path prism- prefixed" ;; esac

echo "== prepare: launcher rendering =="
CXL=$(jq -r '.parallax[0].launcher' "$MAN")
[ -f "$CXL" ] && ok "codex launcher file rendered" || bad "codex launcher file rendered"
head -1 "$CXL" | grep -q '^CRITICAL:' && ok "launcher starts with anti-recursion CRITICAL line" || bad "launcher CRITICAL line"
! grep -q '{{' "$CXL" && ok "no surviving {{slots}} in launcher" || bad "no surviving {{slots}}"
grep -qF "$PKT" "$CXL" && ok "shared_packet path substituted into launcher" || bad "packet path substituted"
grep -q 'Temporal' "$CXL" && ok "lens name substituted into launcher" || bad "lens name substituted"
# Template-by-style: codex renders <goal>, costar peers render <objective>.
DSL=$(jq -r '.parallax[1].launcher' "$MAN")
grep -q '<goal>' "$CXL" && ok "codex launcher uses <goal> scaffolding" || bad "codex <goal> scaffolding"
grep -q '<objective>' "$DSL" && ok "costar launcher uses <objective> scaffolding" || bad "costar <objective> scaffolding"
SAL=$(jq -r '.subagents[0].launcher' "$MAN")
[ -f "$SAL" ] && ok "subagent launcher file rendered" || bad "subagent launcher file rendered"
echo "$SAL" | grep -q 'launcher-subagent-simplicity.md' && ok "subagent lens slugified into filename" || bad "subagent slug filename"

echo "== prepare + dry-run: a 3-peer subset (mixed-tier guard; legacy — not the N=1 default) =="
PKT4="$TMP/prism-run4.md"; make_packet "$PKT4"
CFG4="$TMP/run4-config.json"
jq -n --arg p "$PKT4" '{shared_packet:$p,parallax:[{to:"codex",name:"a",effort:"medium",lens:"Adversarial",lens_desc:"d1"},{to:"deepseek",name:"b",lens:"Completeness",lens_desc:"d2"},{to:"mimo",name:"c",lens:"Consistency",lens_desc:"d3"}],subagents:[{lens:"Correctness",lens_desc:"d5"}]}' > "$CFG4"
expect_ok "prepare accepts all three parallax tiers together" "$LAUNCH" prepare --config "$CFG4"
MAN4="$TMP/prism-run4-manifest.json"
[ "$(jq -r '.counts.parallax_total' "$MAN4" 2>/dev/null)" = "3" ] && ok "three-tier counts: parallax_total=3" || bad "three-tier counts"
DRY4=$("$LAUNCH" parallax "$MAN4" --dry-run 2>/dev/null)
[ "$(echo "$DRY4" | grep -c 'relay call --to')" = "3" ] && ok "three-tier dry-run lists exactly 3 relay calls" || bad "three-tier dry-run lists 3 relay calls"

echo "== prepare: default seven-tier shape + canonical display order =="
PKT5="$TMP/prism-run5.md"; make_packet "$PKT5"
CFG5="$TMP/run5-config.json"
# tiers deliberately scrambled in the config; the dispatch-shape display must still be canonical
jq -n --arg p "$PKT5" '{shared_packet:$p,parallax:[{to:"mimo",name:"a",lens:"L1",lens_desc:"d"},{to:"codex",name:"b",effort:"medium",lens:"L2",lens_desc:"d"},{to:"kimi",name:"g",lens:"L8",lens_desc:"d"},{to:"glm",name:"f",lens:"L7",lens_desc:"d"},{to:"deepseek",name:"c",lens:"L3",lens_desc:"d"},{to:"grok-composer",name:"d",lens:"L4",lens_desc:"d"},{to:"grok-build",name:"e",effort:"high",lens:"L5",lens_desc:"d"}],subagents:[{lens:"L6",lens_desc:"d"}]}' > "$CFG5"
OUT5=$("$LAUNCH" prepare --config "$CFG5" 2>/dev/null)
MAN5="$TMP/prism-run5-manifest.json"
[ "$(jq -r '.counts.parallax_total' "$MAN5" 2>/dev/null)" = "7" ] && ok "default seven-tier counts: parallax_total=7" || bad "seven-tier counts"
echo "$OUT5" | grep -q 'dispatch shape: subagents=1 codex=1 grok-build=1 grok-composer=1 glm=1 kimi=1 deepseek=1 mimo=1' && ok "dispatch shape printed in canonical order (not alphabetical)" || bad "dispatch shape canonical order"

echo "== prepare + dry-run: grok parallax tiers (effort vs no-knob) =="
PKTG="$TMP/prism-grok.md"; make_packet "$PKTG"
# grok-build (effort high) + grok-composer (no effort) accepted together
CFGG="$TMP/grok-config.json"
jq -n --arg p "$PKTG" '{shared_packet:$p,parallax:[{to:"grok-build",name:"gb",effort:"high",lens:"Adversarial",lens_desc:"d1"},{to:"grok-composer",name:"gc",lens:"Outsider",lens_desc:"d2"}],subagents:[]}' > "$CFGG"
expect_ok "prepare accepts grok-build (effort high) + grok-composer (no effort)" "$LAUNCH" prepare --config "$CFGG"
MANG="$TMP/prism-grok-manifest.json"
[ "$(jq -r '.parallax[0].effort' "$MANG" 2>/dev/null)" = "high" ] && ok "grok-build effort = high" || bad "grok-build effort = high"
[ "$(jq -r '.parallax[0].template' "$MANG" 2>/dev/null)" = "costar" ] && ok "grok-build uses costar template (registry)" || bad "grok-build template = costar"
[ "$(jq -r '.counts.by_peer."grok-build"' "$MANG" 2>/dev/null)" = "1" ] && ok "grok-build count = 1" || bad "grok-build count = 1"
[ "$(jq -r '.parallax[1].effort' "$MANG" 2>/dev/null)" = "null" ] && ok "grok-composer effort is null" || bad "grok-composer effort is null"
[ "$(jq -r '.parallax[1].template' "$MANG" 2>/dev/null)" = "costar" ] && ok "grok-composer uses costar template (registry)" || bad "grok-composer template = costar"
[ "$(jq -r '.counts.by_peer."grok-composer"' "$MANG" 2>/dev/null)" = "1" ] && ok "grok-composer count = 1" || bad "grok-composer count = 1"

# Effort is no longer authored. Via the lenient --config path, any leftover .effort is
# IGNORED and the top tier is derived from the registry (grok-build → high, last of [medium,high]).
PKTGE="$TMP/prism-grokge.md"; make_packet "$PKTGE"
CGE="$TMP/grok-badeffort.json"; jq -n --arg p "$PKTGE" '{shared_packet:$p,parallax:[{to:"grok-build",name:"x",effort:"xhigh",lens:"L",lens_desc:"d"}],subagents:[]}' > "$CGE"
expect_ok "ignores authored effort in --config (grok-build)" "$LAUNCH" prepare --config "$CGE"
[ "$(jq -r '.parallax[0].effort' "$TMP/prism-grokge-manifest.json" 2>/dev/null)" = "high" ] && ok "grok-build derives high despite authored 'xhigh'" || bad "grok-build derives high"

# a no-knob peer (grok-composer, no effort_values) derives null even with a leftover .effort
PKTGC="$TMP/prism-grokgc.md"; make_packet "$PKTGC"
CGC="$TMP/grok-composer-effort.json"; jq -n --arg p "$PKTGC" '{shared_packet:$p,parallax:[{to:"grok-composer",name:"x",effort:"high",lens:"L",lens_desc:"d"}],subagents:[]}' > "$CGC"
expect_ok "ignores authored effort on a no-knob peer (--config)" "$LAUNCH" prepare --config "$CGC"
[ "$(jq -r '.parallax[0].effort' "$TMP/prism-grokgc-manifest.json" 2>/dev/null)" = "null" ] && ok "grok-composer effort null despite authored 'high'" || bad "grok-composer effort null"

# dry-run: grok-build carries --effort high; grok-composer carries no --effort.
# The rejection cases above re-ran prepare on the same packet, which clears prior
# artifacts (one packet = one run) — regenerate the valid manifest first.
"$LAUNCH" prepare --config "$CFGG" >/dev/null 2>&1
DRYG=$("$LAUNCH" parallax "$MANG" --dry-run 2>/dev/null)
echo "$DRYG" | grep -q 'relay call --to grok-build --name prism-gb --effort high' && ok "grok-build dry-run cmd has --effort high" || bad "grok-build dry-run --effort high"
echo "$DRYG" | grep -q 'relay call --to grok-composer --name prism-gc <' && ok "grok-composer dry-run cmd has no --effort" || bad "grok-composer dry-run no --effort"

echo "== prepare: negative cases (fail-closed) =="
# missing a still-required section (## Context) → fail-closed
P2="$TMP/p2.md"; printf '## Full Question\nq\n' > "$P2"
C2="$TMP/c2.json"; jq -n --arg p "$P2" '{shared_packet:$p,parallax:[],subagents:[{lens:"X",lens_desc:"y"}]}' > "$C2"
expect_err "rejects packet missing a required section (## Context)" "$LAUNCH" prepare --config "$C2"
# F1: the missing-section error is actionable — prints the copy-paste skeleton, not just the section
# name. Capture first (prepare exits non-zero → pipefail would mask the grep match).
F1ERR=$("$LAUNCH" prepare --config "$C2" 2>&1 || true)
printf '%s\n' "$F1ERR" | grep -q 'nest ALL domain content here as ### subsections' && ok "missing-## Context error prints an actionable skeleton" || bad "missing-section error not actionable"

# missing ## Constraints → prepare INJECTS the canonical block (not a failure)
P2c="$TMP/p2c.md"; printf '## Full Question\nq\n\n## Context\nc\n' > "$P2c"
C2c="$TMP/c2c.json"; jq -n --arg p "$P2c" '{shared_packet:$p,parallax:[],subagents:[{lens:"Xc",lens_desc:"y"}]}' > "$C2c"
expect_ok "injects canonical Constraints when the packet omits them" "$LAUNCH" prepare --config "$C2c"
{ grep -q '^## Constraints' "$P2c" && grep -q 'read-only leaf node' "$P2c"; } && ok "packet gained the verbatim Constraints" || bad "Constraints not injected into packet"
# idempotent: re-running prepare must not double-inject
"$LAUNCH" prepare --config "$C2c" >/dev/null 2>&1
[ "$(grep -c '^## Constraints' "$P2c")" = "1" ] && ok "Constraints injection is idempotent (no double on re-run)" || bad "Constraints double-injected on re-run"
# How-to-answer block: injected alongside Constraints (P2c has now run prepare twice), once, AFTER Constraints
{ grep -q '^## How to answer' "$P2c" && [ "$(grep -c '^## How to answer' "$P2c")" = "1" ]; } && ok "How-to-answer injected once (idempotent)" || bad "How-to-answer missing or double-injected"
[ "$(grep -n '^## Constraints' "$P2c" | cut -d: -f1)" -lt "$(grep -n '^## How to answer' "$P2c" | cut -d: -f1)" ] && ok "How-to-answer is injected after Constraints" || bad "How-to-answer not ordered after Constraints"
# bespoke ## How to answer is left untouched and does NOT fail closed (no safety load, unlike Constraints)
P2h="$TMP/p2h.md"; printf '## Full Question\nq\n\n## Context\nc\n\n## How to answer\nBespoke answer style.\n' > "$P2h"
C2h="$TMP/c2h.json"; jq -n --arg p "$P2h" '{shared_packet:$p,parallax:[],subagents:[{lens:"Xh",lens_desc:"y"}]}' > "$C2h"
expect_ok "accepts a bespoke ## How to answer (no fail-closed)" "$LAUNCH" prepare --config "$C2h"
grep -q 'Bespoke answer style.' "$P2h" && ok "bespoke How-to-answer left untouched" || bad "bespoke How-to-answer was overwritten"
# present-but-abbreviated ## Constraints (missing the anti-recursion guard) → fail-closed
P2a="$TMP/p2a.md"; printf '## Full Question\nq\n\n## Context\nc\n\n## Constraints\nBe nice.\n' > "$P2a"
C2a="$TMP/c2a.json"; jq -n --arg p "$P2a" '{shared_packet:$p,parallax:[],subagents:[{lens:"Xa",lens_desc:"y"}]}' > "$C2a"
expect_err "rejects a ## Constraints section missing the anti-recursion guard" "$LAUNCH" prepare --config "$C2a"

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

# authored effort in --config is ignored (no-knob peer derives null; the derivation never reads .effort)
PKTC5="$TMP/prism-c5.md"; make_packet "$PKTC5"
C5="$TMP/c5.json"; jq -n --arg p "$PKTC5" '{shared_packet:$p,parallax:[{to:"deepseek",name:"x",effort:"xhigh",lens:"L",lens_desc:"d"}],subagents:[]}' > "$C5"
expect_ok "ignores authored effort on deepseek (--config)" "$LAUNCH" prepare --config "$C5"
[ "$(jq -r '.parallax[0].effort' "$TMP/prism-c5-manifest.json" 2>/dev/null)" = "null" ] && ok "deepseek effort null despite authored 'xhigh'" || bad "deepseek effort null"

# authored codex effort in --config is ignored; derivation always wins (xhigh, not the authored 'high')
PKTC6="$TMP/prism-c6.md"; make_packet "$PKTC6"
C6="$TMP/c6.json"; jq -n --arg p "$PKTC6" '{shared_packet:$p,parallax:[{to:"codex",name:"x",effort:"high",lens:"L",lens_desc:"d"}],subagents:[]}' > "$C6"
expect_ok "ignores authored codex effort (--config)" "$LAUNCH" prepare --config "$C6"
[ "$(jq -r '.parallax[0].effort' "$TMP/prism-c6-manifest.json" 2>/dev/null)" = "xhigh" ] && ok "codex derives xhigh despite authored 'high'" || bad "codex derives xhigh"

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
echo "$DRY" | grep -q 'relay call --to codex --name prism-temporal --effort xhigh' && ok "codex dry-run cmd has --effort xhigh (derived)" || bad "codex dry-run --effort"
echo "$DRY" | grep -q 'relay call --to deepseek --name prism-first-principles <' && ok "deepseek dry-run cmd has no --effort" || bad "deepseek dry-run no --effort"
[ -f "$TMP/prism-run1-result.json" ] && bad "dry-run must NOT write a result file" || ok "dry-run writes no result file"

echo "== prepare --dispatch: happy path (line-oriented front-end) =="
PKTD="$TMP/prism-rund.md"; make_packet "$PKTD"
DISP="$TMP/prism-rund.dispatch"
cat > "$DISP" <<DSP
Shared-Packet: $PKTD
Prism-Mode: partial
Partial-User-Quote: "just codex, deepseek, and a claude subagent"

# a comment line, ignored
Type: parallax
To: codex
Name: adversarial
Lens: Adversarial
Lens-Desc: weigh the "strongest" attacks: braces {x} and < > are fine

Type: parallax
To: deepseek
Lens: First-Principles
Lens-Desc: reason from fundamentals

Type: subagent
Lens: Simplicity
Lens-Desc: weigh fewest moving parts
DSP
expect_ok "prepare --dispatch succeeds" "$LAUNCH" prepare --dispatch "$DISP"
MAND="$TMP/prism-rund-manifest.json"
[ -f "$MAND" ] && ok "dispatch: manifest written" || bad "dispatch: manifest written"
[ -f "$TMP/prism-rund-config.normalized.json" ] && ok "dispatch: normalized config written for audit" || bad "dispatch: normalized config written"
jq -e '.parallax[0].lens == "Adversarial" and .subagents[0].lens == "Simplicity"' "$TMP/prism-rund-config.normalized.json" >/dev/null 2>&1 && ok "dispatch: normalized config has expected shape" || bad "dispatch: normalized config shape"
[ "$(jq -r '.counts.dispatched_total' "$MAND" 2>/dev/null)" = "3" ] && ok "dispatch: dispatched_total = 3" || bad "dispatch: dispatched_total = 3"
[ "$(jq -r '.parallax[0].effort' "$MAND" 2>/dev/null)" = "xhigh" ] && ok "dispatch: codex effort derived xhigh (none authored)" || bad "dispatch: codex effort derived xhigh"
[ "$(jq -r '.parallax[0].name' "$MAND" 2>/dev/null)" = "prism-adversarial" ] && ok "dispatch: explicit Name used" || bad "dispatch: explicit Name used"
[ "$(jq -r '.parallax[1].name' "$MAND" 2>/dev/null)" = "prism-first-principles" ] && ok "dispatch: Name derived from Lens when omitted" || bad "dispatch: Name derived from Lens"
[ "$(jq -r '.parallax[1].effort' "$MAND" 2>/dev/null)" = "null" ] && ok "dispatch: deepseek effort null" || bad "dispatch: deepseek effort null"
DLAUNCH=$(jq -r '.parallax[0].launcher' "$MAND")
grep -qF 'braces {x} and < > are fine' "$DLAUNCH" && ok "dispatch: quote/brace/colon desc rendered verbatim (no escaping)" || bad "dispatch: desc rendered verbatim"

echo "== prepare --dispatch: negative cases (fail-closed) =="
expect_err "rejects --config and --dispatch together" "$LAUNCH" prepare --config "$CFG" --dispatch "$DISP"

DNP="$TMP/dnp.dispatch"; printf 'Type: subagent\nLens: X\nLens-Desc: y\n' > "$DNP"
expect_err "rejects dispatch missing Shared-Packet" "$LAUNCH" prepare --dispatch "$DNP"

DUK="$TMP/duk.dispatch"; printf 'Shared-Packet: %s\n\nType: subagent\nModel: codex\nLens: X\nLens-Desc: y\n' "$PKTD" > "$DUK"
expect_err "rejects dispatch unknown key" "$LAUNCH" prepare --dispatch "$DUK"

DBT="$TMP/dbt.dispatch"; printf 'Shared-Packet: %s\n\nTo: codex\nType: parallax\nLens: X\nLens-Desc: y\n' "$PKTD" > "$DBT"
expect_err "rejects dispatch key before any Type record" "$LAUNCH" prepare --dispatch "$DBT"

# Effort is no longer authored: the parser hard-rejects any Effort: line up front.
DED="$TMP/ded.dispatch"; printf 'Shared-Packet: %s\n\nType: parallax\nTo: codex\nEffort: x\nLens: X\nLens-Desc: y\n' "$PKTD" > "$DED"
expect_err "rejects an authored Effort: line in a dispatch (parser-level)" "$LAUNCH" prepare --dispatch "$DED"

DRP="$TMP/drp.dispatch"; printf 'Shared-Packet: relative/path.md\n\nType: subagent\nLens: X\nLens-Desc: y\n' > "$DRP"
expect_err "rejects dispatch relative Shared-Packet" "$LAUNCH" prepare --dispatch "$DRP"

# distinct lens names that slugify identically — caught by the new subagent-slug guard
DSC="$TMP/dsc.dispatch"; printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "test subset"\n\nType: subagent\nLens: First Principles\nLens-Desc: a\n\nType: subagent\nLens: First-Principles\nLens-Desc: b\n' "$PKTD" > "$DSC"
expect_err "rejects subagent lens slug collision" "$LAUNCH" prepare --dispatch "$DSC"

echo "== prepare --dispatch: hardening from review (fail-closed + parity) =="
# duplicate key within one record must fail closed (silent last-wins overwrite otherwise)
DDK="$TMP/ddk.dispatch"; printf 'Shared-Packet: %s\n\nType: parallax\nTo: codex\nLens: A\nLens: B\nLens-Desc: d\n' "$PKTD" > "$DDK"
expect_err "rejects duplicate key within one record" "$LAUNCH" prepare --dispatch "$DDK"

# parallax-only keys on a subagent record (silent wrong-dispatch otherwise)
DST="$TMP/dst.dispatch"; printf 'Shared-Packet: %s\n\nType: subagent\nTo: codex\nLens: X\nLens-Desc: y\n' "$PKTD" > "$DST"
expect_err "rejects To/Name on a subagent record" "$LAUNCH" prepare --dispatch "$DST"

# all-whitespace Lens-Desc via dispatch (trim -> empty -> rejected)
DWS="$TMP/dws.dispatch"; printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "test subset"\n\nType: subagent\nLens: X\nLens-Desc:    \n' "$PKTD" > "$DWS"
expect_err "rejects all-whitespace Lens-Desc (dispatch)" "$LAUNCH" prepare --dispatch "$DWS"

# parity: all-whitespace lens_desc via --config must now also be rejected
CWS="$TMP/cws.json"; jq -n --arg p "$PKTD" '{shared_packet:$p,parallax:[],subagents:[{lens:"X",lens_desc:"   "}]}' > "$CWS"
expect_err "rejects all-whitespace lens_desc (--config parity)" "$LAUNCH" prepare --config "$CWS"

# subagent lens that slugifies to the empty string -> degenerate filename
DES="$TMP/des.dispatch"; printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "test subset"\n\nType: subagent\nLens: !!!\nLens-Desc: y\n' "$PKTD" > "$DES"
expect_err "rejects subagent lens that slugifies to empty" "$LAUNCH" prepare --dispatch "$DES"

# injection guard must not be bypassable via the dispatch path
DIN="$TMP/din.dispatch"; printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "test subset"\n\nType: subagent\nLens: X\nLens-Desc: discuss the {{SLOT}} marker\n' "$PKTD" > "$DIN"
expect_err "injection guard ({{) not bypassable via dispatch" "$LAUNCH" prepare --dispatch "$DIN"

echo "== prepare --dispatch: effort is CLI-derived, never authored =="
# A dispatch with NO Effort line still derives the top tier per peer. This is the core
# regression guard: it catches both the old default_effort fallback (would give medium)
# and the lexicographic-max bug (would give grok-build medium, since "high" < "medium").
PKTE="$TMP/prism-rune.md"; make_packet "$PKTE"
DEF="$TMP/def.dispatch"; printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "just codex and grok-build"\n\nType: parallax\nTo: codex\nLens: Adversarial\nLens-Desc: d\n\nType: parallax\nTo: grok-build\nLens: Structural\nLens-Desc: d\n' "$PKTE" > "$DEF"
expect_ok "prepare --dispatch with no Effort lines" "$LAUNCH" prepare --dispatch "$DEF"
MANE="$TMP/prism-rune-manifest.json"
[ "$(jq -r '.parallax[0].effort' "$MANE" 2>/dev/null)" = "xhigh" ] && ok "dispatch: codex derives xhigh from registry (none authored)" || bad "dispatch: codex derives xhigh"
[ "$(jq -r '.parallax[1].effort' "$MANE" 2>/dev/null)" = "high" ] && ok "dispatch: grok-build derives high (NOT lexicographic medium)" || bad "dispatch: grok-build derives high"

# subagents-only dispatch exercises the empty-parallax accumulator ([], not an error)
PKTZ="$TMP/prism-runz.md"; make_packet "$PKTZ"
DZ="$TMP/dz.dispatch"; printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "claude subagents only"\n\nType: subagent\nLens: Simplicity\nLens-Desc: fewest parts\n' "$PKTZ" > "$DZ"
expect_ok "accepts a subagents-only dispatch (empty parallax accumulator)" "$LAUNCH" prepare --dispatch "$DZ"
[ "$(jq -r '.counts.parallax_total' "$TMP/prism-runz-manifest.json" 2>/dev/null)" = "0" ] && ok "dispatch: empty parallax accumulator -> parallax_total 0" || bad "dispatch: empty parallax -> 0"

echo "== scaffold: symmetric dispatch skeleton =="
SC=$("$LAUNCH" scaffold --n 1 --packet /tmp/prism-sc.md)
[ "$(printf '%s\n' "$SC" | grep -c '^Type:')" = "8" ] && ok "scaffold --n 1 emits 8 records" || bad "scaffold n=1 record count"
printf '%s\n' "$SC" | grep -q '^Shared-Packet: /tmp/prism-sc.md' && ok "scaffold honors --packet" || bad "scaffold --packet"
printf '%s\n' "$SC" | grep -q '^To: codex' && printf '%s\n' "$SC" | grep -q '^To: mimo' && printf '%s\n' "$SC" | grep -q '^To: glm' && printf '%s\n' "$SC" | grep -q '^To: kimi' && ok "scaffold lists all seven parallax tiers" || bad "scaffold tiers"
SCX=$("$LAUNCH" scaffold --n 2)
[ "$(printf '%s\n' "$SCX" | grep -c '^Type:')" = "16" ] && ok "scaffold --n 2 emits 16 records" || bad "scaffold n=2 record count"
# effort is CLI-derived, never authored — scaffold must emit ZERO Effort: lines
[ "$(printf '%s\n' "$SCX" | grep -c '^Effort:')" = "0" ] && ok "scaffold emits no Effort: lines (effort is CLI-derived)" || bad "scaffold no Effort lines"
expect_err "scaffold rejects --effort (no longer an option)" "$LAUNCH" scaffold --effort h
# a filled scaffold round-trips through prepare
make_packet /tmp/prism-scrt.md
"$LAUNCH" scaffold --n 1 --packet /tmp/prism-scrt.md \
  | sed 's/^Lens: FILL-1$/Lens: L1/;s/^Lens: FILL-2$/Lens: L2/;s/^Lens: FILL-3$/Lens: L3/;s/^Lens: FILL-4$/Lens: L4/;s/^Lens: FILL-5$/Lens: L5/;s/^Lens: FILL-6$/Lens: L6/;s/^Lens: FILL-7$/Lens: L7/;s/^Lens: FILL-8$/Lens: L8/;s/^Lens-Desc: FILL$/Lens-Desc: weigh it/' > /tmp/prism-scrt.dispatch
expect_ok "a filled scaffold round-trips through prepare" "$LAUNCH" prepare --dispatch /tmp/prism-scrt.dispatch
# a half-filled scaffold (leftover FILL-<n> lens) must be rejected, not dispatched
make_packet /tmp/prism-schalf.md
"$LAUNCH" scaffold --n 1 --packet /tmp/prism-schalf.md \
  | sed 's/^Lens-Desc: FILL$/Lens-Desc: weigh it/' > /tmp/prism-schalf.dispatch   # descs filled, lens names left as FILL-<n>
expect_err "prepare rejects a half-filled scaffold (leftover FILL placeholder)" "$LAUNCH" prepare --dispatch /tmp/prism-schalf.dispatch
rm -f /tmp/prism-sc* /tmp/prism-scrt* /tmp/prism-schalf*

echo "== clean: removes run artifacts, refuses unsafe targets =="
touch /tmp/prism-cleantest.md /tmp/prism-cleantest-manifest.json /tmp/prism-cleantest-launcher-x.md
"$LAUNCH" clean /tmp/prism-cleantest.md >/dev/null
[ ! -e /tmp/prism-cleantest.md ] && [ ! -e /tmp/prism-cleantest-manifest.json ] && ok "clean removes /tmp/prism-<id>* by packet path" || bad "clean by path"
touch /tmp/prism-cleanid-manifest.json
"$LAUNCH" clean cleanid >/dev/null
[ ! -e /tmp/prism-cleanid-manifest.json ] && ok "clean removes by bare run id" || bad "clean by id"
expect_err "clean refuses an empty/whole-prefix target" "$LAUNCH" clean prism-
expect_err "clean requires a target" "$LAUNCH" clean
# safety: glob / .. / slash in the target must be refused BEFORE any rm (the blocker)
SENTINEL=/tmp/prism-DONOTDELETE-sentinel.md; touch "$SENTINEL"
expect_err "clean refuses a glob target ('*')"      "$LAUNCH" clean '*'
expect_err "clean refuses a glob target ('a*')"     "$LAUNCH" clean 'a*'
expect_err "clean refuses a '..' traversal target"  "$LAUNCH" clean '/tmp/prism-../../etc/x.md'
expect_err "clean refuses a '/' in the run id"      "$LAUNCH" clean 'foo/bar'
[ -e "$SENTINEL" ] && ok "clean left unrelated /tmp/prism-* files intact" || bad "clean glob-injection wiped sentinel"; rm -f "$SENTINEL"
# a manifest path is stripped to the run base, not a partial clean
touch /tmp/prism-mtest.md /tmp/prism-mtest-manifest.json /tmp/prism-mtest-launcher-x.md
"$LAUNCH" clean /tmp/prism-mtest-manifest.json >/dev/null
[ ! -e /tmp/prism-mtest.md ] && [ ! -e /tmp/prism-mtest-launcher-x.md ] && ok "clean by manifest path strips suffix and clears the whole run" || bad "clean manifest-path partial clean"; rm -f /tmp/prism-mtest*

echo "== scaffold --preset: pre-filled, dispatchable lenses =="
SCP=$("$LAUNCH" scaffold --preset review --packet /tmp/prism-pp.md)
[ "$(printf '%s\n' "$SCP" | grep -c FILL)" = "0" ] && ok "scaffold --preset leaves no FILL placeholder" || bad "preset has FILL"
[ "$(printf '%s\n' "$SCP" | grep -c '^Type:')" = "8" ] && ok "scaffold --preset emits 8 records (N=1)" || bad "preset record count"
printf '%s\n' "$SCP" | grep -q '^Lens: Adversarial' && ok "preset 'review' puts a heavy lens on slot 1" || bad "preset slot-1 lens"
expect_err "scaffold rejects an unknown --preset" "$LAUNCH" scaffold --preset nope
expect_err "scaffold rejects --preset with --n > 1" "$LAUNCH" scaffold --n 2 --preset review
# a preset scaffold round-trips through prepare (lenses are valid, not FILL)
printf '## Full Question\nq\n\n## Context\nc\n' > /tmp/prism-pp.md
"$LAUNCH" scaffold --preset review --packet /tmp/prism-pp.md > /tmp/prism-pp.dispatch
expect_ok "a preset scaffold round-trips through prepare" "$LAUNCH" prepare --dispatch /tmp/prism-pp.dispatch
# --out writes a prepare-ready dispatch directly (no Write/Edit by the agent → no Read trap)
SCOUT="$TMP/scout.dispatch"; SCOUTPKT="$TMP/prism-scout.md"
printf '## Full Question\nq\n\n## Context\nc\n' > "$SCOUTPKT"
expect_ok "scaffold --out writes a preset dispatch to a file" "$LAUNCH" scaffold --preset review --packet "$SCOUTPKT" --out "$SCOUT"
{ [ -f "$SCOUT" ] && [ "$(grep -c '^Type:' "$SCOUT")" = "8" ] && grep -q "^Shared-Packet: $SCOUTPKT" "$SCOUT"; } && ok "scaffold --out file is a complete 8-record dispatch with the real packet" || bad "scaffold --out content"
expect_ok "scaffold --out file is directly prepare-ready (no edit)" "$LAUNCH" prepare --dispatch "$SCOUT"
expect_err "scaffold --out requires --preset (a FILL file would force a Read)" "$LAUNCH" scaffold --packet "$SCOUTPKT" --out "$SCOUT"
expect_err "scaffold --out requires --packet (Shared-Packet must be real)" "$LAUNCH" scaffold --preset review --out "$SCOUT"
expect_err "scaffold --out rejects a relative path" "$LAUNCH" scaffold --preset review --packet "$SCOUTPKT" --out rel.dispatch

echo "== scaffold --m / --n 0: gpt-pro-shape-aware (F3/F6) =="
SCM=$("$LAUNCH" scaffold --n 1 --m 2)
printf '%s\n' "$SCM" | grep -q '^Prism-M: 2' && ok "scaffold --m sets Prism-M" || bad "scaffold --m Prism-M"
[ "$(printf '%s\n' "$SCM" | grep -c '^Type: gpt-pro')" = "2" ] && ok "scaffold --m 2 emits 2 gpt-pro records" || bad "scaffold --m gpt-pro count"
{ printf '%s\n' "$SCM" | grep -q '^Posture: deep-reasoning' && printf '%s\n' "$SCM" | grep -q '^Posture: research-grounded'; } && ok "scaffold --m emits canonical postures" || bad "scaffold --m postures"
# M>2: the default gpt-pro lens names must stay distinct (suffixed), or prepare's duplicate-lens check bounces
SCM3LENS=$("$LAUNCH" scaffold --n 1 --m 3 | awk '/^Type: gpt-pro/{g=1;next} g&&/^Lens:/{print;g=0}')
{ [ "$(printf '%s\n' "$SCM3LENS" | wc -l | tr -d ' ')" = "3" ] && [ "$(printf '%s\n' "$SCM3LENS" | sort -u | wc -l | tr -d ' ')" = "3" ] && printf '%s\n' "$SCM3LENS" | grep -q 'Deep-Reasoning-3'; } && ok "scaffold --m 3 gpt-pro lens names stay distinct (suffix at M>2)" || bad "scaffold --m 3 distinct names"
# gpt-pro-only: --n 0 --m M emits no standard records, only gpt-pro
SC0=$("$LAUNCH" scaffold --n 0 --m 1)
{ printf '%s\n' "$SC0" | grep -q '^Prism-N: 0' \
  && [ "$(printf '%s\n' "$SC0" | grep -c '^Type: parallax')" = "0" ] \
  && [ "$(printf '%s\n' "$SC0" | grep -c '^Type: subagent')" = "0" ] \
  && [ "$(printf '%s\n' "$SC0" | grep -c '^Type: gpt-pro')" = "1" ]; } \
  && ok "scaffold --n 0 --m 1 = gpt-pro-only (no standard records)" || bad "scaffold --n 0 shape"
expect_err "scaffold --n 0 without --m is rejected (gpt-pro-only needs M>=1)" "$LAUNCH" scaffold --n 0
expect_err "scaffold --m rejects a non-integer" "$LAUNCH" scaffold --m x
# preset + --m stays zero-FILL and round-trips through prepare
SCMPKT="$TMP/prism-scm.md"; printf '## Full Question\nq\n\n## Context\nc\n' > "$SCMPKT"
SCMOUT="$TMP/scm.dispatch"
"$LAUNCH" scaffold --preset review --m 1 --packet "$SCMPKT" --out "$SCMOUT" 2>/dev/null
{ [ "$(grep -c FILL "$SCMOUT")" = "0" ] && [ "$(grep -c '^Type: gpt-pro' "$SCMOUT")" = "1" ]; } && ok "scaffold --preset --m stays zero-FILL with a gpt-pro record" || bad "scaffold preset --m"
expect_ok "scaffold --preset --m round-trips through prepare" "$LAUNCH" prepare --dispatch "$SCMOUT"
# a gpt-pro-only scaffold (--n 0 --m, default postures are valid lenses) round-trips through prepare
SC0PKT="$TMP/prism-sc0.md"; printf '## Full Question\nq\n\n## Context\nc\n' > "$SC0PKT"
SC0OUT="$TMP/sc0.dispatch"
"$LAUNCH" scaffold --n 0 --m 2 --packet "$SC0PKT" 2>/dev/null > "$SC0OUT"
expect_ok "scaffold --n 0 --m round-trips through prepare (gpt-pro-only)" "$LAUNCH" prepare --dispatch "$SC0OUT"

# prepare prints the expected-notification count (capture first — grep -q on the pipe would SIGPIPE prepare mid-dump)
"$LAUNCH" prepare --dispatch /tmp/prism-pp.dispatch >"$TMP/ppnotif.out" 2>/dev/null
grep -q 'wait for 2 completion notification' "$TMP/ppnotif.out" && ok "prepare prints the expected-notification count" || bad "notification-count line"

echo "== parallax --only: single-peer retry targeting (dry-run) =="
MPP=/tmp/prism-pp-manifest.json
"$LAUNCH" parallax "$MPP" --only codex --dry-run 2>/dev/null | grep -q 'relay call --to codex --name prism-correctness' && ok "--only matches a peer by model" || bad "--only by model"
"$LAUNCH" parallax "$MPP" --only outsider --dry-run 2>/dev/null | grep -q 'relay call --to kimi --name prism-outsider' && ok "--only matches a peer by lens slug" || bad "--only by slug"
"$LAUNCH" parallax "$MPP" --only prism-correctness --dry-run 2>/dev/null | grep -q 'relay call --to codex' && ok "--only matches a peer by relay name" || bad "--only by name"
expect_err "--only refuses an unknown peer" "$LAUNCH" parallax "$MPP" --only nope --dry-run

echo "== parallax --only: real (fake-relay) retry + merge, fail-closed =="
# Build a fake skill tree so prism-launch resolves a STUB relay sibling (no network,
# no recursion). This exercises the real merge path the dry-run tests can't reach.
FT="$TMP/ft"; mkdir -p "$FT/prism/scripts" "$FT/relay/scripts"
cp "$LAUNCH" "$FT/prism/scripts/prism-launch"
ln -s "$HERE/../templates"        "$FT/prism/templates"
ln -s "$HERE/../../relay/peers.json" "$FT/relay/peers.json"
cat > "$FT/relay/scripts/relay" <<'FAKE'
#!/usr/bin/env bash
name=""; while [ $# -gt 0 ]; do case "$1" in --name) name="${2:-}"; shift 2 ;; *) shift ;; esac; done
res="$(cd "$(dirname "$0")/.." && pwd)/FAKE-$name.res.md"; echo "fake response body" > "$res"
echo "relay: response → $res" >&2
FAKE
chmod +x "$FT/relay/scripts/relay"
FL="$FT/prism/scripts/prism-launch"
FPK="$TMP/prism-fakeonly.md"; printf '## Full Question\nq\n\n## Context\nc\n' > "$FPK"
printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "just codex and deepseek"\n\nType: parallax\nTo: codex\nLens: Alpha\nLens-Desc: weigh a\n\nType: parallax\nTo: deepseek\nLens: Beta\nLens-Desc: weigh b\n' "$FPK" > "$TMP/fakeonly.dispatch"
"$FL" prepare --dispatch "$TMP/fakeonly.dispatch" >/dev/null 2>&1
FMAN="$TMP/prism-fakeonly-manifest.json"; FRES="$TMP/prism-fakeonly-result.json"
"$FL" parallax "$FMAN" >/dev/null 2>&1
{ [ "$(jq '.results|length' "$FRES" 2>/dev/null)" = "2" ] && [ "$(jq '.succeeded' "$FRES" 2>/dev/null)" = "2" ]; } && ok "fake fan wrote a 2-peer result" || bad "fake fan result"
"$FL" parallax "$FMAN" --only codex >/dev/null 2>&1
{ [ "$(jq '.results|length' "$FRES")" = "2" ] && [ "$(jq '[.results[]|select(.name=="prism-alpha")]|length' "$FRES")" = "1" ]; } && ok "--only retry replaces one peer (no dup; count stays 2)" || bad "--only merge replace"
# fail-closed: an EMPTY existing result + a MULTI-peer manifest must REFUSE a single-peer
# rewrite (it would read as falsely complete) — re-run the whole fan instead.
: > "$FRES"; expect_err "--only refuses a single-peer rewrite over an empty result (multi-peer manifest)" "$FL" parallax "$FMAN" --only codex
# a MALFORMED existing result likewise refuses
printf 'not json{' > "$FRES"; expect_err "--only refuses a single-peer rewrite over a malformed result (multi-peer manifest)" "$FL" parallax "$FMAN" --only codex
# carve-out: a SINGLE-peer manifest may legitimately write a fresh result over an empty one
FPK1="$TMP/prism-fake1.md"; printf '## Full Question\nq\n\n## Context\nc\n' > "$FPK1"
printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "just codex"\n\nType: parallax\nTo: codex\nLens: Solo\nLens-Desc: weigh s\n' "$FPK1" > "$TMP/fake1.dispatch"
"$FL" prepare --dispatch "$TMP/fake1.dispatch" >/dev/null 2>&1
FMAN1="$TMP/prism-fake1-manifest.json"; FRES1="$TMP/prism-fake1-result.json"
: > "$FRES1"; "$FL" parallax "$FMAN1" --only codex >/dev/null 2>&1
{ [ -s "$FRES1" ] && jq -e '(.results|type)=="array"' "$FRES1" >/dev/null 2>&1; } && ok "--only writes a fresh result over an empty one for a single-peer manifest" || bad "--only single-peer fresh write"

echo "== results: structured view from result.json =="
# empty/malformed result.json is rejected, not printed as a blank summary
: > /tmp/prism-empty-result.json
printf '{"id":"prism-empty","shared_packet":"/tmp/prism-empty.md"}' > /tmp/prism-empty-manifest.json
expect_err "results rejects an empty result.json" "$LAUNCH" results /tmp/prism-empty-manifest.json
rm -f /tmp/prism-empty*
# Build the result from MPP's ACTUAL parallax set so the completeness gate (result peer
# set must match the manifest) is satisfied; all peers done → exit 0.
jq -c '{id:.id, expected:(.parallax|length), succeeded:(.parallax|length), failed:0,
        results:[.parallax[]|{to:.to, name:.name, status:"done", res:"/tmp/a.res.md", log:"/tmp/a.log"}]}' "$MPP" > /tmp/prism-pp-result.json
RES=$("$LAUNCH" results "$MPP")
printf '%s\n' "$RES" | grep -q '/tmp/a.res.md' && printf '%s\n' "$RES" | grep -q '0 failed' && ok "results prints each peer's .res.md path + summary" || bad "results output"
expect_ok "results exits 0 when all peers complete" "$LAUNCH" results "$MPP"
# A complete result with one peer in error → exit 1 (failure), completeness still satisfied.
jq -c '{id:.id, expected:(.parallax|length),
        results:[.parallax[]|{to:.to, name:.name, status:"done", res:"/tmp/a.res.md", log:"/tmp/a.log"}]}
       | .results[0].status="error" | .results[0].res=null
       | .succeeded=([.results[]|select(.status=="done")]|length) | .failed=([.results[]|select(.status!="done")]|length)' "$MPP" > /tmp/prism-pp-result.json
expect_err "results exits non-zero when a peer failed" "$LAUNCH" results "$MPP"
"$LAUNCH" results "$MPP" >/dev/null 2>&1; rc=$?; [ "$rc" -eq 1 ] && ok "results exits exactly 1 (terminal failure) when a peer errored" || bad "results failure exit code (got $rc, want 1)"
# COMPLETENESS GATE: a result with only some of the manifest's peers must NOT read as done —
# it exits 2 (pending) and flags INCOMPLETE, so a partial result can't bypass the hard gate.
jq -c '{id:.id, expected:1, succeeded:1, failed:0, results:[(.parallax[0])|{to:.to, name:.name, status:"done", res:"/tmp/a.res.md", log:"/tmp/a.log"}]}' "$MPP" > /tmp/prism-pp-result.json
ROUT=$("$LAUNCH" results "$MPP" 2>&1); rc=$?
{ [ "$rc" -eq 2 ] && printf '%s\n' "$ROUT" | grep -q 'INCOMPLETE'; } && ok "results flags a partial result (peers missing vs manifest) INCOMPLETE, exit 2" || bad "results completeness gate (got $rc)"
# #3a: a parallax manifest with NO result file yet is pending (exit 2), not a die/failure.
rm -f /tmp/prism-pp-result.json
"$LAUNCH" results "$MPP" >/dev/null 2>&1; rc=$?; [ "$rc" -eq 2 ] && ok "results exits 2 (pending) when the parallax result file is absent" || bad "results missing-result exit (got $rc, want 2)"
printf '{"id":"prism-nores","shared_packet":"/tmp/prism-nores.md"}' > /tmp/prism-nores-manifest.json
expect_err "results errors on a manifest with no parallax/gpt-pro/subagent entries" "$LAUNCH" results /tmp/prism-nores-manifest.json
"$LAUNCH" clean pp >/dev/null; rm -f /tmp/prism-nores*
# #3b: a subagents-only manifest has no file-backed lanes — results is a clean no-op (exit 0)
SOMAN="$TMP/prism-subonly-manifest.json"
printf '{"id":"prism-subonly","shared_packet":"%s","subagents":[{"lens":"Simplicity"}],"parallax":[],"gpt-pro":[],"counts":{"subagents":1,"parallax_total":0,"gpt-pro":0}}' "$TMP/prism-subonly.md" > "$SOMAN"
SOUT=$("$LAUNCH" results "$SOMAN" 2>&1); rc=$?
{ [ "$rc" -eq 0 ] && printf '%s\n' "$SOUT" | grep -q 'subagents-only'; } && ok "results: subagents-only manifest is a clean no-op (exit 0)" || bad "results subagents-only (got $rc)"

echo "== digest: extract ## Digest blocks (lineage-tagged, compaction-only) =="
DGP="$TMP/prism-dg.md"            # packet path only used to derive sibling artifact paths
DGMAN="$TMP/prism-dg-manifest.json"; DGRES="$TMP/prism-dg-result.json"; DGOUT="$TMP/prism-dg-digest.md"
RA="$TMP/dg-a.res.md"; RB="$TMP/dg-b.res.md"
cat > "$RA" <<'RES'
---
from: codex
---
Long analysis body here.
More reasoning.

## Digest
- Position: pick option B
- Key reasons: removes shared state
- Dissent/caveat: none
- Changes if: p99 > 50ms
RES
printf -- '---\nfrom: grok-composer\n---\nBody with no digest section at all.\n' > "$RB"
printf '{"id":"prism-dg","shared_packet":"%s"}' "$DGP" > "$DGMAN"
printf '{"id":"prism-dg","expected":3,"succeeded":2,"failed":1,"results":[{"to":"codex","name":"prism-alpha","status":"done","res":"%s","log":"/tmp/a.log"},{"to":"grok-composer","name":"prism-beta","status":"done","res":"%s","log":"/tmp/b.log"},{"to":"mimo","name":"prism-gamma","status":"error","res":null,"log":"/tmp/c.log"}]}' "$RA" "$RB" > "$DGRES"
expect_ok "digest succeeds on a finished run" "$LAUNCH" digest "$DGMAN"
[ -f "$DGOUT" ] && ok "digest writes <id>-digest.md by default" || bad "digest output file"
grep -q 'Position: pick option B' "$DGOUT" && ok "digest extracts the ## Digest block body" || bad "digest extracts block"
! grep -q 'Long analysis body here' "$DGOUT" && ok "digest omits the full answer body (compaction)" || bad "digest leaked full body"
grep -q 'lineage: grok' "$DGOUT"  && ok "digest collapses grok-composer to the grok lineage" || bad "digest grok lineage"
grep -q 'lineage: codex' "$DGOUT" && ok "digest tags the codex lineage" || bad "digest codex lineage"
grep -q 'block found'  "$DGOUT" && ok "digest flags a peer with no ## Digest block" || bad "digest missing-block note"
grep -q 'peer failed'  "$DGOUT" && ok "digest flags a failed peer" || bad "digest failed-peer note"
grep -qF "$RA" "$DGOUT" && ok "digest cites the full .res.md path for deep-reads" || bad "digest cites res path"
"$LAUNCH" digest "$DGMAN" --out "$TMP/dg-custom.md" >/dev/null 2>&1
[ -f "$TMP/dg-custom.md" ] && ok "digest honors --out" || bad "digest --out"
printf '{"id":"prism-dgx","shared_packet":"%s"}' "$TMP/prism-dgx.md" > "$TMP/prism-dgx-manifest.json"
expect_err "digest errors when no result file exists yet" "$LAUNCH" digest "$TMP/prism-dgx-manifest.json"
: > "$TMP/prism-dgm-result.json"; printf '{"id":"prism-dgm","shared_packet":"%s"}' "$TMP/prism-dgm.md" > "$TMP/prism-dgm-manifest.json"
expect_err "digest rejects an empty result.json" "$LAUNCH" digest "$TMP/prism-dgm-manifest.json"

echo "== digest: hardened extraction edge cases (fence/colon/nested/multiple/%) =="
DHP="$TMP/prism-dh.md"; DHMAN="$TMP/prism-dh-manifest.json"; DHRES="$TMP/prism-dh-result.json"; DHOUT="$TMP/prism-dh-digest.md"
# fenced whole digest + trailing prose: must NOT leak the trailing prose (degrades to a miss)
RC="$TMP/dh-fenced.res.md"; cat > "$RC" <<'RES'
Intro body.

```
## Digest
- Position: fenced position only
```

LEAKED-TRAILING-PROSE-MUST-NOT-APPEAR
RES
# `## Digest:` with a trailing colon must still extract
RD="$TMP/dh-colon.res.md"; printf '## Digest:\n- Position: colon-variant-captured\n- Changes if: none\n' > "$RD"
# a deeper `###` inside the digest must NOT truncate it
RN="$TMP/dh-nested.res.md"; printf '## Digest\n- Position: nested-test\n### sub-note\n- Changes if: still-here-after-subheading\n' > "$RN"
# two `## Digest` headings: the LAST one wins (template says "end your answer with")
RM="$TMP/dh-multi.res.md"; printf 'Draft:\n## Digest\n- Position: FIRST-draft-should-lose\nRevised. Final:\n## Digest\n- Position: SECOND-final-should-win\n' > "$RM"
# `%` and backtick in the body survive (printf '%s' regression guard)
RP="$TMP/dh-percent.res.md"; printf '## Digest\n- Position: 100%% coverage with `jq` parsing\n- Changes if: none\n' > "$RP"
printf '{"id":"prism-dh","shared_packet":"%s"}' "$DHP" > "$DHMAN"
jq -n --arg rc "$RC" --arg rd "$RD" --arg rn "$RN" --arg rm "$RM" --arg rp "$RP" \
  '{id:"prism-dh",expected:5,succeeded:5,failed:0,results:[
    {to:"codex",name:"prism-fenced",status:"done",res:$rc,log:"/tmp/x.log"},
    {to:"deepseek",name:"prism-colon",status:"done",res:$rd,log:"/tmp/x.log"},
    {to:"mimo",name:"prism-nested",status:"done",res:$rn,log:"/tmp/x.log"},
    {to:"grok-composer",name:"prism-multi",status:"done",res:$rm,log:"/tmp/x.log"},
    {to:"grok-build",name:"prism-percent",status:"done",res:$rp,log:"/tmp/x.log"}
  ]}' > "$DHRES"
"$LAUNCH" digest "$DHMAN" >/dev/null 2>&1
! grep -q 'LEAKED-TRAILING-PROSE' "$DHOUT" && ok "fenced digest does not leak trailing prose (degrades to a miss)" || bad "fenced digest leaked trailing prose"
grep -q 'colon-variant-captured'        "$DHOUT" && ok "extracts a '## Digest:' colon-variant heading" || bad "colon-variant missed"
grep -q 'still-here-after-subheading'   "$DHOUT" && ok "a nested ### does not truncate the digest" || bad "nested ### truncated the digest"
grep -q 'SECOND-final-should-win'       "$DHOUT" && ! grep -q 'FIRST-draft-should-lose' "$DHOUT" && ok "multiple ## Digest: the last one wins" || bad "multiple-digest last-wins"
grep -q '100% coverage with `jq`'       "$DHOUT" && ok "percent + backtick in body survive (printf '%s' safe)" || bad "percent/backtick body mangled"

echo "== prepare: clears a stale -digest.md on re-run =="
make_packet "$TMP/prism-stale.md"
printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "subagent only"\n\nType: subagent\nLens: Xstale\nLens-Desc: y\n' "$TMP/prism-stale.md" > "$TMP/stale.dispatch"
"$LAUNCH" prepare --dispatch "$TMP/stale.dispatch" >/dev/null 2>&1
touch "$TMP/prism-stale-digest.md"
"$LAUNCH" prepare --dispatch "$TMP/stale.dispatch" >/dev/null 2>&1
[ ! -e "$TMP/prism-stale-digest.md" ] && ok "re-prepare clears a stale -digest.md" || bad "stale -digest.md not cleared on re-prepare"

echo "== gpt-pro: compose-in-prepare (config .references is authoritative) =="
GPK="$TMP/prism-gp.md"; printf '## Full Question\nFuse the thing.\n\n## Context\nSome context.\n' > "$GPK"
REF1="$TMP/ref-one.md";  printf 'REF-ONE-CONTENT-MARKER\nl2\n' > "$REF1"
REF2="$TMP/ref-two.txt"; printf 'REF-TWO-CONTENT-MARKER\n'     > "$REF2"
GCFG="$TMP/gp-config.json"
jq -n --arg p "$GPK" --arg r1 "$REF1" --arg r2 "$REF2" \
  '{shared_packet:$p, references:[$r1,$r2],
    parallax:[{to:"codex",name:"adv",effort:"medium",lens:"Adversarial",lens_desc:"attack it"}],
    subagents:[{lens:"Simplicity",lens_desc:"fewest parts"}],
    "gpt-pro":[{lens:"Deep-Reasoning",lens_desc:"reason deeply",posture:"deep-reasoning"}]}' > "$GCFG"
GOUT=$("$LAUNCH" prepare --config "$GCFG" 2>/dev/null)
GMAN="$TMP/prism-gp-manifest.json"
[ -f "$GMAN" ] && ok "gpt-pro: manifest written" || bad "gpt-pro: manifest written"
[ "$(jq -r '.counts."gpt-pro"' "$GMAN" 2>/dev/null)" = "1" ] && ok "gpt-pro: counts.gpt-pro = 1" || bad "gpt-pro count"
[ "$(jq -r '.counts.dispatched_total' "$GMAN" 2>/dev/null)" = "2" ] && ok "gpt-pro: dispatched_total excludes gpt-pro (subagent+parallax=2)" || bad "gpt-pro dispatched_total"
[ "$(jq -r '."gpt-pro"[0].slug' "$GMAN" 2>/dev/null)" = "deep-reasoning" ] && ok "gpt-pro: lens slugified" || bad "gpt-pro slug"
[ "$(jq -r '."gpt-pro"[0].posture' "$GMAN" 2>/dev/null)" = "deep-reasoning" ] && ok "gpt-pro: posture carried" || bad "gpt-pro posture"
GLAUNCH=$(jq -r '."gpt-pro"[0].launcher' "$GMAN")
[ -f "$GLAUNCH" ] && ok "gpt-pro: launcher composed" || bad "gpt-pro launcher composed"
head -1 "$GLAUNCH" | grep -q '^CRITICAL:' && ok "gpt-pro: launcher starts with CRITICAL guard" || bad "gpt-pro CRITICAL"
! grep -q '{{' "$GLAUNCH" && ok "gpt-pro: no surviving {{slots}}" || bad "gpt-pro slots"
grep -q 'Deep-Reasoning' "$GLAUNCH" && ok "gpt-pro: lens name substituted" || bad "gpt-pro lens sub"
grep -q 'Fuse the thing.' "$GLAUNCH" && ok "gpt-pro: frozen packet inlined verbatim" || bad "gpt-pro packet inlined"
{ grep -q 'REF-ONE-CONTENT-MARKER' "$GLAUNCH" && grep -q 'REF-TWO-CONTENT-MARKER' "$GLAUNCH"; } && ok "gpt-pro: reference CONTENTS inlined (not paths)" || bad "gpt-pro refs inlined"
grep -qF "### $REF1" "$GLAUNCH" && ok "gpt-pro: each ref under its ### path header" || bad "gpt-pro ref header"
{ grep -q 'Grounding external facts' "$GLAUNCH" && grep -q '## Calibration' "$GLAUNCH"; } && ok "gpt-pro: grounding (via packet) + calibration present" || bad "gpt-pro grounding/calibration"
[ "$(grep -c '^## Grounding external facts' "$GPK")" = "1" ] && ok "grounding: injected once into the shared packet (reaches all agents)" || bad "grounding packet count != 1"
[ "$(grep -c '^## Grounding external facts' "$GLAUNCH")" = "1" ] && ok "gpt-pro: grounding inherited from packet exactly once (no double)" || bad "gpt-pro grounding count != 1"
echo "$GOUT" | grep -q 'gpt-pro=1' && ok "gpt-pro: dispatch shape shows gpt-pro=1" || bad "gpt-pro dispatch shape"
echo "$GOUT" | grep -q 'one per gpt-pro lens' && ok "gpt-pro: notification count includes gpt-pro" || bad "gpt-pro notif count"
echo "$GOUT" | grep -qF "gpt-pro < $GLAUNCH" && ok "gpt-pro: prints the exact backgrounded launch command" || bad "gpt-pro launch line"
# the printed launch command records the exit code to a .exit sidecar so results can tell failed from pending
echo "$GOUT" | grep -qF 'printf %s "$?" >' && echo "$GOUT" | grep -q '\.exit' && ok "gpt-pro: launch line records the exit code to a .exit sidecar" || bad "gpt-pro exit-sentinel print"

echo "== gpt-pro: --dispatch front-end + Reference keys + packet fallback =="
GPKB="$TMP/prism-gpb.md"
printf '## Full Question\nq\n\n## Context\nc\n\n### Reference Materials\n- %s\n' "$REF1" > "$GPKB"
GDISP="$TMP/gpb.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nPrism-M: 1\n\nType: gpt-pro\nLens: Falsification\nLens-Desc: try to break it\n' "$GPKB" > "$GDISP"
expect_ok "gpt-pro: --dispatch with packet ### Reference Materials fallback" "$LAUNCH" prepare --dispatch "$GDISP"
GMANB="$TMP/prism-gpb-manifest.json"
GLB=$(jq -r '."gpt-pro"[0].launcher' "$GMANB")
grep -q 'REF-ONE-CONTENT-MARKER' "$GLB" && ok "gpt-pro: packet ### Reference Materials list resolved + inlined" || bad "gpt-pro packet-list fallback"
# explicit Reference: keys win and may include a 'none' opt-out (own packet -> own manifest)
GPKB2="$TMP/prism-gpb2.md"
printf '## Full Question\nq\n\n## Context\nc\n\n### Reference Materials\n- %s\n' "$REF1" > "$GPKB2"
GDISP2="$TMP/gpb2.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nPrism-M: 1\nReference: none\n\nType: gpt-pro\nLens: Falsification\nLens-Desc: d\n' "$GPKB2" > "$GDISP2"
expect_ok "gpt-pro: 'Reference: none' inlines only the packet" "$LAUNCH" prepare --dispatch "$GDISP2"
GLB2=$(jq -r '."gpt-pro"[0].launcher' "$TMP/prism-gpb2-manifest.json")
! grep -q 'REF-ONE-CONTENT-MARKER' "$GLB2" && ok "gpt-pro: 'Reference: none' skips the packet list (no refs inlined)" || bad "gpt-pro Reference none"

echo "== gpt-pro: fail-closed validation =="
# gpt-pro lens but NO reference source at all -> NOT a bounce: a self-contained packet is
# valid gpt-pro input, so prepare defaults to packet-only and WARNS loudly (F2). The hard
# error is reserved for an explicitly DECLARED bad reference (the cases below).
GPKN="$TMP/prism-gpn.md"; printf '## Full Question\nq\n\n## Context\nc\n' > "$GPKN"
GDN="$TMP/gpn.dispatch"; printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nPrism-M: 1\n\nType: gpt-pro\nLens: X\nLens-Desc: y\n' "$GPKN" > "$GDN"
GNERR=$("$LAUNCH" prepare --dispatch "$GDN" 2>&1); GNRC=$?
[ "$GNRC" -eq 0 ] && ok "gpt-pro: no reference source -> packet-only default, not a bounce" || bad "gpt-pro no-ref default exit (got $GNRC)"
printf '%s\n' "$GNERR" | grep -q 'shared packet ONLY' && ok "gpt-pro: no-reference run warns loudly (packet-only)" || bad "gpt-pro no-ref warning"
GLN=$(jq -r '."gpt-pro"[0].launcher' "$TMP/prism-gpn-manifest.json" 2>/dev/null)
{ [ -f "$GLN" ] && grep -q '^## Full Question' "$GLN" && ! grep -q '^### .*ref-one' "$GLN"; } && ok "gpt-pro: packet-only launcher composed (packet inlined, no refs)" || bad "gpt-pro no-ref launcher"
# review fix: a packet-only launcher must NOT carry a dangling "Inlined reference materials" heading
! grep -q 'Inlined reference materials' "$GLN" && ok "gpt-pro: packet-only launcher omits the dangling reference heading" || bad "gpt-pro packet-only dangling heading"
# review fix: a ### Reference Materials heading with NO valid absolute bullets (empty / all-relative)
# must also default to packet-only AND warn — never silently (the old elif branch was silent).
GPKE="$TMP/prism-gpe.md"; printf '## Full Question\nq\n\n## Context\nc\n\n### Reference Materials\n\n- relative/not-absolute.md\n' > "$GPKE"
GDE2="$TMP/gpe2.dispatch"; printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nPrism-M: 1\n\nType: gpt-pro\nLens: Z\nLens-Desc: y\n' "$GPKE" > "$GDE2"
GEERR=$("$LAUNCH" prepare --dispatch "$GDE2" 2>&1); GERC=$?
[ "$GERC" -eq 0 ] && ok "gpt-pro: empty/malformed ### Reference Materials -> packet-only (not a bounce)" || bad "gpt-pro empty-RM exit (got $GERC)"
printf '%s\n' "$GEERR" | grep -q 'NO reference files resolved' && ok "gpt-pro: empty/malformed ### Reference Materials WARNS (no silent packet-only)" || bad "gpt-pro empty-RM warning"
# directory reference
GCD="$TMP/gpd.json"; jq -n --arg p "$GPKN" --arg d "$TMP" '{shared_packet:$p,references:[$d],parallax:[],subagents:[],"gpt-pro":[{lens:"X",lens_desc:"y"}]}' > "$GCD"
expect_err "gpt-pro: a directory Reference -> fail-closed" "$LAUNCH" prepare --config "$GCD"
# missing reference
GCM="$TMP/gpm.json"; jq -n --arg p "$GPKN" --arg m "$TMP/does-not-exist.md" '{shared_packet:$p,references:[$m],parallax:[],subagents:[],"gpt-pro":[{lens:"X",lens_desc:"y"}]}' > "$GCM"
expect_err "gpt-pro: a missing Reference -> fail-closed" "$LAUNCH" prepare --config "$GCM"
# relative reference
GCR="$TMP/gpr.json"; jq -n --arg p "$GPKN" '{shared_packet:$p,references:["relative/ref.md"],parallax:[],subagents:[],"gpt-pro":[{lens:"X",lens_desc:"y"}]}' > "$GCR"
expect_err "gpt-pro: a relative Reference -> fail-closed" "$LAUNCH" prepare --config "$GCR"
# whitespace in reference path
GCW="$TMP/gpw.json"; jq -n --arg p "$GPKN" --arg w "$TMP/has space.md" '{shared_packet:$p,references:[$w],parallax:[],subagents:[],"gpt-pro":[{lens:"X",lens_desc:"y"}]}' > "$GCW"
expect_err "gpt-pro: a whitespace Reference path -> fail-closed" "$LAUNCH" prepare --config "$GCW"
# oversize reference (> 5MB cap)
BIGREF="$TMP/big.ref"; head -c 5100000 /dev/zero | tr '\0' 'x' > "$BIGREF"
GCB="$TMP/gpbig.json"; jq -n --arg p "$GPKN" --arg b "$BIGREF" '{shared_packet:$p,references:[$b],parallax:[],subagents:[],"gpt-pro":[{lens:"X",lens_desc:"y"}]}' > "$GCB"
expect_err "gpt-pro: an over-5MB Reference -> fail-closed before launch" "$LAUNCH" prepare --config "$GCB"
# To/Name/Effort on a gpt-pro dispatch record
GDE="$TMP/gpe.dispatch"; printf 'Shared-Packet: %s\nReference: none\n\nType: gpt-pro\nEffort: x\nLens: X\nLens-Desc: y\n' "$GPKB" > "$GDE"
expect_err "gpt-pro: rejects an authored Effort line (no longer authored)" "$LAUNCH" prepare --dispatch "$GDE"
# bad posture
GCP="$TMP/gpp.json"; jq -n --arg p "$GPKB" '{shared_packet:$p,references:[],parallax:[],subagents:[],"gpt-pro":[{lens:"X",lens_desc:"y",posture:"wrong"}]}' > "$GCP"
expect_err "gpt-pro: rejects an invalid posture" "$LAUNCH" prepare --config "$GCP"
# duplicate lens across the run (subagent + gpt-pro share a name)
GCDUP="$TMP/gpdup.json"; jq -n --arg p "$GPKB" '{shared_packet:$p,references:[],parallax:[],subagents:[{lens:"Same",lens_desc:"d"}],"gpt-pro":[{lens:"Same",lens_desc:"d"}]}' > "$GCDUP"
expect_err "gpt-pro: rejects a lens name shared with a subagent" "$LAUNCH" prepare --config "$GCDUP"
# One canonical dispatch Type spelling: the hyphenated 'gpt-pro'. The hyphen-less 'gptpro'
# and underscore 'gpt_pro' spellings are REJECTED with a hint (not silently normalized), so
# the record Type matches its 'gpt-pro' lens-list key exactly. Otherwise-valid dispatch so
# the only thing under test is the spelling.
GHYP="$TMP/gpt-hyphen.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nPrism-M: 1\n\nType: gpt-pro\nLens: X\nLens-Desc: y\n' "$GPKB" > "$GHYP"
expect_ok "gpt-pro: accepts the canonical 'Type: gpt-pro' (hyphenated)" "$LAUNCH" prepare --dispatch "$GHYP"
[ "$(jq -r '.counts."gpt-pro"' "$GMANB" 2>/dev/null)" = "1" ] && ok "gpt-pro: 'Type: gpt-pro' produces a gpt-pro record" || bad "gpt-pro record from canonical Type"
GHL="$TMP/gpt-hyphenless.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nPrism-M: 1\n\nType: gptpro\nLens: X\nLens-Desc: y\n' "$GPKB" > "$GHL"
expect_err "gpt-pro: rejects the hyphen-less 'Type: gptpro' (no longer an alias)" "$LAUNCH" prepare --dispatch "$GHL"
# Pin the DEDICATED rejection branch, not just non-zero exit: the hint text lives only in the
# gptpro|gpt_pro) case, so this fails if that case is deleted (the generic *) branch also dies).
# Capture first — prepare exits non-zero, so a `prepare | grep` pipeline would mask the match under pipefail.
GHLERR=$("$LAUNCH" prepare --dispatch "$GHL" 2>&1)
printf '%s\n' "$GHLERR" | grep -qF "spelled 'gpt-pro' (hyphenated)" \
  && ok "gpt-pro: 'Type: gptpro' rejection carries the migration hint" || bad "gpt-pro gptpro hint text"
GUND="$TMP/gpt-under.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nPrism-M: 1\n\nType: gpt_pro\nLens: X\nLens-Desc: y\n' "$GPKB" > "$GUND"
expect_err "gpt-pro: rejects the underscore 'Type: gpt_pro' (no longer an alias)" "$LAUNCH" prepare --dispatch "$GUND"
GUNDERR=$("$LAUNCH" prepare --dispatch "$GUND" 2>&1)
printf '%s\n' "$GUNDERR" | grep -qF "spelled 'gpt-pro' (hyphenated)" \
  && ok "gpt-pro: 'Type: gpt_pro' rejection carries the migration hint" || bad "gpt-pro gpt_pro hint text"
# The lenient --config raw-JSON path fail-closes on a MISSPELLED lens-list key: a hyphen-less
# "gptpro" / underscore "gpt_pro" key is silently ignored, so a mixed run (parallax present)
# would otherwise pass the zero-records guard and drop the whole gpt-pro lane with no error.
# The canonical hyphenated "gpt-pro" key is accepted.
GCKEYOK="$TMP/gp-goodkey.json"
jq -n --arg p "$GPKN" '{shared_packet:$p,references:[],parallax:[],subagents:[],"gpt-pro":[{lens:"X",lens_desc:"y"}]}' > "$GCKEYOK"
expect_ok "gpt-pro: --config accepts the canonical 'gpt-pro' lens-list key" "$LAUNCH" prepare --config "$GCKEYOK"
GCKEY="$TMP/gp-badkey.json"
jq -n --arg p "$GPKN" '{shared_packet:$p,references:[],parallax:[{to:"codex",name:"adv",lens:"Adversarial",lens_desc:"attack it"}],subagents:[],"gptpro":[{lens:"X",lens_desc:"y"}]}' > "$GCKEY"
expect_err "gpt-pro: --config rejects a hyphen-less 'gptpro' lens-list key (would silently drop the lane)" "$LAUNCH" prepare --config "$GCKEY"
GCKEY2="$TMP/gp-badkey2.json"
jq -n --arg p "$GPKN" '{shared_packet:$p,references:[],parallax:[{to:"codex",name:"adv",lens:"Adversarial",lens_desc:"attack it"}],subagents:[],"gpt_pro":[{lens:"X",lens_desc:"y"}]}' > "$GCKEY2"
expect_err "gpt-pro: --config rejects an underscore 'gpt_pro' lens-list key (would silently drop the lane)" "$LAUNCH" prepare --config "$GCKEY2"

echo "== gpt-pro: gpt-pro-only run + results/digest/clean lanes =="
GPKO="$TMP/prism-gpo.md"; printf '## Full Question\nq\n\n## Context\nc\n' > "$GPKO"
GCO="$TMP/gpo.json"; jq -n --arg p "$GPKO" '{shared_packet:$p,references:[],parallax:[],subagents:[],"gpt-pro":[{lens:"Deep",lens_desc:"d"}]}' > "$GCO"
expect_ok "gpt-pro: a gpt-pro-only run prepares (no parallax/subagents)" "$LAUNCH" prepare --config "$GCO"
GMANO="$TMP/prism-gpo-manifest.json"
GRES=$(jq -r '."gpt-pro"[0].res' "$GMANO"); GLOG=$(jq -r '."gpt-pro"[0].log' "$GMANO")
# pending: no .res.md yet, a .log with a run_id -> results surfaces it, exits non-zero
printf 'gpt-pro: run_id=ask-20260618-abc transport=ssh mode=submit\n' > "$GLOG"
expect_err "gpt-pro: results exits non-zero while a lens is pending" "$LAUNCH" results "$GMANO"
"$LAUNCH" results "$GMANO" >/dev/null 2>&1; rc=$?; [ "$rc" -eq 2 ] && ok "gpt-pro: results exits exactly 2 (pending, not failure) while a lens is pending" || bad "results pending exit code (got $rc, want 2)"
# results exits non-zero while pending, so capture first (pipefail would mask the grep)
RUNOUT=$("$LAUNCH" results "$GMANO" 2>/dev/null || true)
printf '%s\n' "$RUNOUT" | grep -q 'run_id=ask-20260618-abc' && ok "gpt-pro: results surfaces the pending run_id for reattach" || bad "gpt-pro results run_id"
# #2: a recorded .exit (the launch wrapper) with an empty .res.md = finished-but-FAILED,
# not 'pending' — results must report [FAILED] and exit 1, never passive pending (2).
GEXIT="${GRES%.res.md}.exit"; printf '124\n' > "$GEXIT"
GFOUT=$("$LAUNCH" results "$GMANO" 2>&1); rc=$?
{ [ "$rc" -eq 1 ] && printf '%s\n' "$GFOUT" | grep -q 'FAILED'; } && ok "gpt-pro: a recorded non-zero .exit with no .res.md reports FAILED, exit 1 (not pending)" || bad "gpt-pro exit-sentinel results (got $rc)"
rm -f "$GEXIT"
# completed: .res.md present -> results exits 0, digest extracts the block tagged gpt-pro
cat > "$GRES" <<'RES'
Body of the gpt-pro answer.

## Digest
- Position: GPTPRO-DIGEST-MARKER
- Changes if: none
RES
expect_ok "gpt-pro: results exits 0 once the lens .res.md is present" "$LAUNCH" results "$GMANO"
"$LAUNCH" digest "$GMANO" >/dev/null 2>&1
GDGO="$TMP/prism-gpo-digest.md"
grep -q 'GPTPRO-DIGEST-MARKER' "$GDGO" && ok "gpt-pro: digest extracts the gpt-pro ## Digest block" || bad "gpt-pro digest extract"
grep -q 'lineage: gpt-pro' "$GDGO" && ok "gpt-pro: digest tags the gpt-pro lineage" || bad "gpt-pro digest lineage"
# phantom-parallax guard: a stale/unrelated result.json must NOT add phantom peers to a gpt-pro-only digest
printf '{"id":"prism-gpo","expected":1,"succeeded":1,"failed":0,"results":[{"to":"codex","name":"prism-ghost","status":"done","res":"/tmp/ghost.res.md","log":"/tmp/g.log"}]}' > "$TMP/prism-gpo-result.json"
"$LAUNCH" digest "$GMANO" >/dev/null 2>&1
{ ! grep -q 'prism-ghost' "$GDGO" && ! grep -q 'lineage: codex' "$GDGO"; } && ok "gpt-pro: gpt-pro-only digest ignores a stale result.json (no phantom peers)" || bad "gpt-pro digest phantom peers"
grep -q 'GPTPRO-DIGEST-MARKER' "$GDGO" && ok "gpt-pro: gpt-pro-only digest still emits the gpt-pro lens despite a stale result.json" || bad "gpt-pro digest dropped gpt-pro lane"
rm -f "$TMP/prism-gpo-result.json"
# clean guard: a .log with a run_id but NO .res.md is a possibly-live worker -> refuse.
# clean only operates on /tmp/prism-* (its safety prefix), so use a real /tmp run here.
GPKC=/tmp/prism-gpcg.md; printf '## Full Question\nq\n\n## Context\nc\n' > "$GPKC"
GCC="$TMP/gpc.json"; jq -n --arg p "$GPKC" '{shared_packet:$p,references:[],parallax:[],subagents:[],"gpt-pro":[{lens:"Deep",lens_desc:"d"}]}' > "$GCC"
"$LAUNCH" prepare --config "$GCC" >/dev/null 2>&1
GLOGC=$(jq -r '."gpt-pro"[0].log' /tmp/prism-gpcg-manifest.json)
printf 'gpt-pro: run_id=ask-live-xyz transport=ssh\n' > "$GLOGC"
expect_err "gpt-pro: clean refuses a possibly-live run (run_id, no .res.md)" "$LAUNCH" clean /tmp/prism-gpcg.md
expect_ok "gpt-pro: clean --force overrides the live-run guard" "$LAUNCH" clean /tmp/prism-gpcg.md --force
# a completed lens (.res.md present) is safe to clean without --force (re-create packet first)
printf '## Full Question\nq\n\n## Context\nc\n' > "$GPKC"
"$LAUNCH" prepare --config "$GCC" >/dev/null 2>&1
GLOGC=$(jq -r '."gpt-pro"[0].log' /tmp/prism-gpcg-manifest.json); GRESC=$(jq -r '."gpt-pro"[0].res' /tmp/prism-gpcg-manifest.json)
printf 'gpt-pro: run_id=ask-done-xyz transport=ssh\n' > "$GLOGC"; printf 'answer\n' > "$GRESC"
expect_ok "gpt-pro: clean allows a completed run (run_id + non-empty .res.md)" "$LAUNCH" clean /tmp/prism-gpcg.md
rm -f /tmp/prism-gpcg*

echo "== subcommand --help =="
"$LAUNCH" scaffold --help 2>/dev/null | grep -q 'Usage:' && ok "scaffold --help prints usage" || bad "scaffold --help"

echo "== prepare: roster-enforcement contract (default-on floor + partial waiver) =="
FPKT="$TMP/prism-floor.md"; make_packet "$FPKT"
# scaffold now EMITS the contract (Prism-Mode: full / Prism-N: 1) — full is the easy path.
"$LAUNCH" scaffold --preset review --packet "$FPKT" > "$TMP/prism-floor.dispatch"
grep -q '^Prism-Mode: full' "$TMP/prism-floor.dispatch" && ok "scaffold emits Prism-Mode: full" || bad "scaffold emits Prism-Mode"
grep -q '^Prism-N: 1'       "$TMP/prism-floor.dispatch" && ok "scaffold emits Prism-N"       || bad "scaffold emits Prism-N"
# a full preset (all 8 tiers) passes the default floor with NO flag at all.
expect_ok "contract: a full preset passes the default floor (no flag)" "$LAUNCH" prepare --dispatch "$TMP/prism-floor.dispatch"
MANFL="$TMP/prism-floor-manifest.json"
[ "$(jq -r '.shape.mode' "$MANFL" 2>/dev/null)" = "full" ] && ok "contract: manifest records shape.mode=full" || bad "manifest shape.mode"
[ "$(jq -r '.shape.validated_roster' "$MANFL" 2>/dev/null)" = "true" ] && ok "contract: manifest records validated_roster=true" || bad "manifest validated_roster"
# CLI --expect-n still OVERRIDES (back-compat): N=2 on an N=1 shape fails, naming the tier.
expect_err "contract: --expect-n 2 overrides the contract and fails an N=1 shape" "$LAUNCH" prepare --dispatch "$TMP/prism-floor.dispatch" --expect-n 2
FERR=$("$LAUNCH" prepare --dispatch "$TMP/prism-floor.dispatch" --expect-n 2 2>&1 || true)
printf '%s' "$FERR" | grep -q 'codex: expected 2, got 1' && ok "contract: floor failure names the under-count tier" || bad "contract floor detail"

# A dispatch with NO Prism-Mode is rejected — the enforced default cannot be dodged by omission.
NOCON="$TMP/prism-nocon.md"; make_packet "$NOCON"
NOCOND="$TMP/prism-nocon.dispatch"
{ printf 'Shared-Packet: %s\n\n' "$NOCON"
  printf 'Type: subagent\nLens: A\nLens-Desc: d\n\n'
  printf 'Type: parallax\nTo: codex\nLens: B\nLens-Desc: d\n\n'; } > "$NOCOND"
expect_err "contract: a dispatch with no Prism-Mode is rejected" "$LAUNCH" prepare --dispatch "$NOCOND"

# Declaring 'full' on an incomplete (2-tier) shape fails the floor, naming a missing tier.
ASF="$TMP/prism-asf.md"; make_packet "$ASF"
ASFD="$TMP/prism-asf.dispatch"
{ printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 1\n\n' "$ASF"
  printf 'Type: subagent\nLens: A\nLens-Desc: d\n\n'
  printf 'Type: parallax\nTo: codex\nLens: B\nLens-Desc: d\n\n'; } > "$ASFD"
expect_err "contract: declaring 'full' on a 2-tier shape fails the floor" "$LAUNCH" prepare --dispatch "$ASFD"
AERR=$("$LAUNCH" prepare --dispatch "$ASFD" 2>&1 || true)
printf '%s' "$AERR" | grep -q 'mimo: expected 1, got 0' && ok "contract: full-on-partial names a missing tier" || bad "contract full-on-partial detail"

# The SAME shape with an authorized partial waiver succeeds and records the quote (double-confirm).
ASW="$TMP/prism-asw.md"; make_packet "$ASW"
ASWD="$TMP/prism-asw.dispatch"
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "use only claude and codex"\n\n' "$ASW"
  printf 'Type: subagent\nLens: A\nLens-Desc: d\n\n'
  printf 'Type: parallax\nTo: codex\nLens: B\nLens-Desc: d\n\n'; } > "$ASWD"
expect_ok "contract: partial + user quote authorizes a reduced roster" "$LAUNCH" prepare --dispatch "$ASWD"
MANASW="$TMP/prism-asw-manifest.json"
[ "$(jq -r '.shape.mode' "$MANASW" 2>/dev/null)" = "partial" ] && ok "contract: partial recorded in manifest" || bad "partial mode in manifest"
[ "$(jq -r '.shape.partial_user_quote' "$MANASW" 2>/dev/null)" = '"use only claude and codex"' ] && ok "contract: user quote recorded verbatim (audit trail)" || bad "partial quote recorded"
[ "$(jq -r '.shape.validated_roster' "$MANASW" 2>/dev/null)" = "false" ] && ok "contract: partial is not a validated full roster" || bad "partial validated flag"
jq -e '.shape.excluded_tiers | index("mimo") != null' "$MANASW" >/dev/null 2>&1 && ok "contract: dropped tiers recorded in manifest" || bad "excluded tiers recorded"
PWARN=$("$LAUNCH" prepare --dispatch "$ASWD" 2>&1 || true)
{ printf '%s' "$PWARN" | grep -q 'PARTIAL prism' && printf '%s' "$PWARN" | grep -q 'use only claude and codex'; } && ok "contract: partial warns loudly with dropped tiers + cited quote" || bad "partial warning"

# Partial WITHOUT a quote is rejected — the double-confirm is mandatory.
PNQ="$TMP/prism-pnq.md"; make_packet "$PNQ"
PNQD="$TMP/prism-pnq.dispatch"
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\n\n' "$PNQ"
  printf 'Type: parallax\nTo: codex\nLens: B\nLens-Desc: d\n\n'; } > "$PNQD"
expect_err "contract: partial without Partial-User-Quote is rejected" "$LAUNCH" prepare --dispatch "$PNQD"

# Invalid Prism-Mode value, and 'full' without Prism-N.
PBM="$TMP/prism-pbm.md"; make_packet "$PBM"
PBMD="$TMP/prism-pbm.dispatch"; { printf 'Shared-Packet: %s\nPrism-Mode: half\nPrism-N: 1\n\n' "$PBM"; printf 'Type: subagent\nLens: A\nLens-Desc: d\n\n'; } > "$PBMD"
expect_err "contract: an invalid Prism-Mode value is rejected" "$LAUNCH" prepare --dispatch "$PBMD"
PNND="$TMP/prism-pnn.dispatch"; { printf 'Shared-Packet: %s\nPrism-Mode: full\n\n' "$PBM"; printf 'Type: subagent\nLens: A\nLens-Desc: d\n\n'; } > "$PNND"
expect_err "contract: Prism-Mode: full without Prism-N is rejected" "$LAUNCH" prepare --dispatch "$PNND"

# gpt-pro-only: full N=0 + M=1 is legal; full N=0 + M=0 is rejected (not a Prism run).
GPKO="$TMP/prism-gponly.md"; make_packet "$GPKO"
GPO="$TMP/prism-gponly.dispatch"
{ printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nPrism-M: 1\nReference: none\n\n' "$GPKO"
  printf 'Type: gpt-pro\nLens: Deep-Reasoning\nLens-Desc: d\n\n'; } > "$GPO"
expect_ok  "contract: gpt-pro-only (full N=0 M=1) passes"  "$LAUNCH" prepare --dispatch "$GPO"
GPO0="$TMP/prism-gponly0.dispatch"
{ printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nPrism-M: 0\nReference: none\n\n' "$GPKO"
  printf 'Type: gpt-pro\nLens: Deep-Reasoning\nLens-Desc: d\n\n'; } > "$GPO0"
expect_err "contract: full N=0 with M=0 is rejected (gpt-pro-only needs M>=1)" "$LAUNCH" prepare --dispatch "$GPO0"

# --config escape hatch stays lenient (no contract required); manifest shape = unchecked.
CLENPKT="$TMP/prism-clen.md"; make_packet "$CLENPKT"
CLEN="$TMP/clen.json"; jq -n --arg p "$CLENPKT" '{shared_packet:$p,parallax:[{to:"codex",name:"a",lens:"L",lens_desc:"d"}],subagents:[]}' > "$CLEN"
expect_ok "contract: --config without a shape stays lenient (escape hatch)" "$LAUNCH" prepare --config "$CLEN"
[ "$(jq -r '.shape.mode' "$TMP/prism-clen-manifest.json" 2>/dev/null)" = "unchecked" ] && ok "contract: lenient --config records shape.mode=unchecked" || bad "lenient config shape"
# --expect-n still works on --config (manual floor / override): 1 tier != full roster -> fail.
CLEN2PKT="$TMP/prism-clen2.md"; make_packet "$CLEN2PKT"
CLEN2="$TMP/clen2.json"; jq -n --arg p "$CLEN2PKT" '{shared_packet:$p,parallax:[{to:"codex",name:"a",lens:"L",lens_desc:"d"}],subagents:[]}' > "$CLEN2"
expect_err "contract: --config + --expect-n 1 floor-checks (1 tier != full roster)" "$LAUNCH" prepare --config "$CLEN2" --expect-n 1
# Flag hygiene retained: --expect-m without --expect-n rejected; non-integer rejected; leading zero ok.
expect_err "contract: --expect-m without --expect-n is rejected" "$LAUNCH" prepare --dispatch "$TMP/prism-floor.dispatch" --expect-m 1
expect_err "contract: --expect-n non-integer is rejected"        "$LAUNCH" prepare --dispatch "$TMP/prism-floor.dispatch" --expect-n foo
expect_ok  "contract: --expect-n 01 (leading zero) parses as 1"  "$LAUNCH" prepare --dispatch "$TMP/prism-floor.dispatch" --expect-n 01

echo "== prepare: review-fix hardening (#1-#6) =="
# #1 — partial + --expect-n must SKIP the floor check (not fail an authorized partial),
# record shape.n=null (not the override value), and stay validated_roster=false.
HP1="$TMP/prism-h1.md"; make_packet "$HP1"
HP1D="$TMP/h1.dispatch"
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "only codex"\n\n' "$HP1"
  printf 'Type: parallax\nTo: codex\nLens: A\nLens-Desc: d\n\n'; } > "$HP1D"
expect_ok "#1: partial + --expect-n succeeds (floor skipped, not a false failure)" "$LAUNCH" prepare --dispatch "$HP1D" --expect-n 1
H1MAN="$TMP/prism-h1-manifest.json"
[ "$(jq -r '.shape.n' "$H1MAN" 2>/dev/null)" = "null" ] && ok "#1: partial records shape.n=null (not the --expect-n value)" || bad "#1 partial shape.n null"
[ "$(jq -r '.shape.validated_roster' "$H1MAN" 2>/dev/null)" = "false" ] && ok "#1: partial stays unvalidated even with --expect-n" || bad "#1 partial validated false"
H1NOTE=$("$LAUNCH" prepare --dispatch "$HP1D" --expect-n 1 2>&1 || true)
printf '%s' "$H1NOTE" | grep -q 'ignoring --expect-n on a Prism-Mode: partial' && ok "#1: notes that --expect-n is ignored on partial" || bad "#1 ignore note"

# #2 — lenient --config with an INCOMPLETE roster warns loudly (and still prepares).
HP2="$TMP/prism-h2.md"; make_packet "$HP2"
HP2C="$TMP/h2.json"; jq -n --arg p "$HP2" '{shared_packet:$p,parallax:[{to:"codex",name:"a",lens:"A",lens_desc:"d"}],subagents:[]}' > "$HP2C"
H2W=$("$LAUNCH" prepare --config "$HP2C" 2>&1)
{ printf '%s' "$H2W" | grep -q 'roster NOT validated' && printf '%s' "$H2W" | grep -q 'INCOMPLETE roster'; } && ok "#2: lenient --config with incomplete roster warns loudly" || bad "#2 unchecked warning"

# #3 — malformed author-supplied --config .shape fails closed.
HP3="$TMP/prism-h3.md"; make_packet "$HP3"
mkbad(){ jq -n --arg p "$HP3" --argjson s "$1" '{shared_packet:$p,shape:$s,parallax:[{to:"codex",name:"a",lens:"A",lens_desc:"d"}],subagents:[]}'; }
mkbad '{"mode":"bogus"}'                                          > "$TMP/h3a.json"; expect_err "#3: --config .shape mode=bogus rejected"                "$LAUNCH" prepare --config "$TMP/h3a.json"
mkbad '{"mode":"full"}'                                           > "$TMP/h3b.json"; expect_err "#3: --config full .shape without n rejected"          "$LAUNCH" prepare --config "$TMP/h3b.json"
mkbad '{"mode":"full","n":1.5}'                                  > "$TMP/h3c.json"; expect_err "#3: --config full .shape non-integer n rejected"      "$LAUNCH" prepare --config "$TMP/h3c.json"
mkbad '{"mode":"partial","n":1,"partial_user_quote":"x"}'        > "$TMP/h3d.json"; expect_err "#3: --config partial .shape with n rejected"          "$LAUNCH" prepare --config "$TMP/h3d.json"
mkbad '{"mode":"partial","partial_user_quote":"   "}'            > "$TMP/h3e.json"; expect_err "#3: --config partial .shape blank quote rejected"      "$LAUNCH" prepare --config "$TMP/h3e.json"

# #4 — a full dispatch omitting Prism-M defaults M to 0 (gpt-pro pinned, not unchecked).
HP4="$TMP/prism-h4.md"; make_packet "$HP4"
"$LAUNCH" scaffold --preset review --packet "$HP4" | grep -v '^Prism-M:' > "$TMP/h4.dispatch"
expect_ok "#4: full dispatch omitting Prism-M still prepares" "$LAUNCH" prepare --dispatch "$TMP/h4.dispatch"
[ "$(jq -r '.shape.m' "$TMP/prism-h4-manifest.json" 2>/dev/null)" = "0" ] && ok "#4: omitted Prism-M defaults to 0 (gpt-pro pinned, not unchecked)" || bad "#4 M defaults to 0"
HP4B="$TMP/prism-h4b.md"; make_packet "$HP4B"
{ printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 0\nReference: none\n\n' "$HP4B"; printf 'Type: gpt-pro\nLens: Deep\nLens-Desc: d\n\n'; } > "$TMP/h4b.dispatch"
expect_err "#4: full N=0 omitting Prism-M is rejected (defaults to 0, needs M>=1)" "$LAUNCH" prepare --dispatch "$TMP/h4b.dispatch"

# #5 — parallax rejects an empty/malformed .shape, not only a missing one.
HP5="$TMP/prism-h5.md"; make_packet "$HP5"
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "only codex"\n\n' "$HP5"; printf 'Type: parallax\nTo: codex\nLens: A\nLens-Desc: d\n\n'; } > "$TMP/h5.dispatch"
"$LAUNCH" prepare --dispatch "$TMP/h5.dispatch" >/dev/null 2>&1
jq '.shape = {}'  "$TMP/prism-h5-manifest.json" > "$TMP/prism-h5b-manifest.json"
expect_err "#5: parallax rejects a manifest with empty .shape {}"   "$LAUNCH" parallax "$TMP/prism-h5b-manifest.json" --dry-run
jq 'del(.shape)' "$TMP/prism-h5-manifest.json" > "$TMP/prism-h5c-manifest.json"
expect_err "#5: parallax rejects a manifest with no .shape key"     "$LAUNCH" parallax "$TMP/prism-h5c-manifest.json" --dry-run

# #6 — duplicate contract keys + non-integer contract values rejected at the parser.
HP6="$TMP/prism-h6.md"; make_packet "$HP6"
printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-Mode: partial\n\nType: subagent\nLens: A\nLens-Desc: d\n' "$HP6" > "$TMP/h6a.dispatch"
expect_err "#6: duplicate Prism-Mode rejected"          "$LAUNCH" prepare --dispatch "$TMP/h6a.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 1\nPrism-N: 2\n\nType: subagent\nLens: A\nLens-Desc: d\n' "$HP6" > "$TMP/h6b.dispatch"
expect_err "#6: duplicate Prism-N rejected"             "$LAUNCH" prepare --dispatch "$TMP/h6b.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "a"\nPartial-User-Quote: "b"\n\nType: parallax\nTo: codex\nLens: A\nLens-Desc: d\n' "$HP6" > "$TMP/h6c.dispatch"
expect_err "#6: duplicate Partial-User-Quote rejected"  "$LAUNCH" prepare --dispatch "$TMP/h6c.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: abc\n\nType: subagent\nLens: A\nLens-Desc: d\n' "$HP6" > "$TMP/h6d.dispatch"
expect_err "#6: non-integer Prism-N rejected (contract path)" "$LAUNCH" prepare --dispatch "$TMP/h6d.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: full\nPrism-N: 1\nPrism-M: 1.5\n\nType: subagent\nLens: A\nLens-Desc: d\n' "$HP6" > "$TMP/h6e.dispatch"
expect_err "#6: non-integer Prism-M rejected (contract path)" "$LAUNCH" prepare --dispatch "$TMP/h6e.dispatch"

echo "== lens catalog: single-source integrity =="
CAT="$HERE/../templates/lens-catalog.json"
jq -e . "$CAT" >/dev/null 2>&1 && ok "catalog is valid JSON" || bad "catalog invalid JSON"
jq -e '(.lenses|map(.name)) as $L | [.presets[][]] | all(. as $n | ($L|index($n)) != null)' "$CAT" >/dev/null 2>&1 \
  && ok "catalog: every preset lens is a defined lens" || bad "catalog: unknown preset lens"
jq -e '.axes as $A | .lenses | all(.axis as $a | ($A|index($a)) != null)' "$CAT" >/dev/null 2>&1 \
  && ok "catalog: every lens axis is a declared family" || bad "catalog: undeclared lens axis"
jq -e '(.lenses|map(.name)) as $N | ($N|length) == ($N|unique|length)' "$CAT" >/dev/null 2>&1 \
  && ok "catalog: lens names are unique" || bad "catalog: duplicate lens name"

echo "== registry: single-source tier order + lineage =="
PJ="$HERE/../../relay/peers.json"
SCO=$("$LAUNCH" scaffold --n 1 --packet /tmp/x.md | awk -F': ' '/^To: /{print $2}' | tr '\n' ' ')
REGO=$(jq -r 'to_entries|map(select(.value.order!=null))|sort_by(.value.order)|.[].key' "$PJ" | tr '\n' ' ')
[ "$SCO" = "$REGO" ] && ok "scaffold parallax order == registry .order" || bad "scaffold order != registry ($SCO vs $REGO)"
[ "$(jq -r '."grok-build".lineage' "$PJ")" = "$(jq -r '."grok-composer".lineage' "$PJ")" ] \
  && ok "registry: grok-build and grok-composer share one lineage" || bad "registry: grok lineage split"
jq -e 'to_entries|map(select(.value.order!=null))|(map(.value.order)) as $O | ($O|length)==($O|unique|length)' "$PJ" >/dev/null 2>&1 \
  && ok "registry: tier .order values are unique" || bad "registry: duplicate .order"
# every standard tier (.order set) must also carry a non-empty .lineage — digest
# lineage derives from it; a missing one would silently split a lineage.
jq -e 'to_entries|map(select(.value.order!=null))|all(.value.lineage|type=="string" and length>0)' "$PJ" >/dev/null 2>&1 \
  && ok "registry: every ordered tier has a non-empty .lineage" || bad "registry: an ordered tier is missing .lineage"
# the single-source invariant the scaffold count-guard enforces at runtime: every
# preset must have exactly (tier count)+1 lenses (one per parallax peer + 1 subagent).
NTIERS=$(jq -r 'to_entries|map(select(.value.order!=null))|length' "$PJ")
jq -e --argjson want "$((NTIERS + 1))" '.presets|to_entries|all(.value|length==$want)' "$CAT" >/dev/null 2>&1 \
  && ok "catalog: every preset has (tier count)+1 lenses" || bad "catalog: a preset's lens count != tiers+1 (scaffold --preset would fail closed)"

echo "== cross-file contracts (drift guards) =="
# The digest extractor greps '^## Digest' in each agent's .res.md; the canonical answer
# template must INSTRUCT agents to use exactly that heading, or every digest silently
# extracts empty. Pin the template's instructed heading so a rename there is caught.
HTA="$HERE/../templates/shared-how-to-answer.md"
grep -qF '## Digest' "$HTA" \
  && ok "contract: shared-how-to-answer.md instructs the '## Digest' heading the extractor greps" \
  || bad "contract: '## Digest' heading missing/renamed in shared-how-to-answer.md (digest extraction would silently zero)"
# prism-launch derives the fixed top effort as effort_values[-1]; pin that the array
# stays ordered weakest->strongest so a future reorder can't silently pick the wrong tier.
[ "$(jq -r '.codex.effort_values[-1]' "$PJ")" = "xhigh" ] \
  && ok "contract: codex effort_values[-1] is the top tier (xhigh)" || bad "contract: codex effort_values ordering ([-1] != xhigh)"
[ "$(jq -r '."grok-build".effort_values[-1]' "$PJ")" = "high" ] \
  && ok "contract: grok-build effort_values[-1] is the top tier (high)" || bad "contract: grok-build effort_values ordering ([-1] != high)"
# gpt-pro run_id recovery is a cross-SKILL string coupling: the gpt-pro wrapper prints
# "gpt-pro: run_id=<id> ..." on stderr, and prism-launch greps '^gpt-pro: run_id=' (clean's
# live-worker guard + results' reattach hint). A spelling/format drift on EITHER side
# silently makes recovery find nothing → abandon/double-submit risk. Pin both sides.
GPWRAP="$HERE/../../gpt-pro-relay/scripts/gpt-pro"
if [ -f "$GPWRAP" ]; then
  grep -qF 'gpt-pro: run_id=' "$GPWRAP" \
    && ok "contract: gpt-pro wrapper emits the 'gpt-pro: run_id=' stderr prefix prism-launch greps" \
    || bad "contract: 'gpt-pro: run_id=' prefix missing/renamed in gpt-pro-relay/scripts/gpt-pro (prism recovery would silently find nothing)"
else
  echo "  SKIP: gpt-pro wrapper not found at $GPWRAP (cross-skill run_id contract unchecked)"
fi
grep -qF '^gpt-pro: run_id=' "$LAUNCH" \
  && ok "contract: prism-launch greps the '^gpt-pro: run_id=' prefix the wrapper emits" \
  || bad "contract: prism-launch no longer greps '^gpt-pro: run_id=' (recovery drift from the wrapper)"

echo "== Include: file front door =="
INCD="$TMP/incsrc"; mkdir -p "$INCD"
printf 'alpha contents\n' > "$INCD/a.md"
printf 'beta contents\n'  > "$INCD/b.md"
printf 'SECRET=zzz\n'      > "$INCD/.env"
# minimal partial-roster dispatch carrying Include:
inc_dispatch() {  # <packet> <extra-records-file-or-empty> ... writes a dispatch on stdout
  local pkt="$1"; shift
  printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "test"\n' "$pkt"
  cat
}
# 1) happy path: two explicit files → resolves, generates region, sets references
PKI="$TMP/inc1.md"; make_packet "$PKI"
{ inc_dispatch "$PKI" <<EOF
Include: $INCD/a.md
Include: $INCD/b.md

Type: subagent
Lens: Simplicity
Lens-Desc: weigh fewest moving parts
EOF
} > "$TMP/inc1.dispatch"
expect_ok "Include: two explicit files prepares" "$LAUNCH" prepare --dispatch "$TMP/inc1.dispatch"
grep -q 'PRISM-INCLUDE-START' "$PKI" \
  && ok "Include: generates the managed ### Reference Materials region" || bad "Include: no generated region"
[ "$(jq -r '.references|length' "$TMP/inc1-config.normalized.json")" = "2" ] \
  && ok "Include: sets config.references to the resolved set" || bad "Include: references not set"

# 2) re-run idempotency: exactly one managed region
"$LAUNCH" prepare --dispatch "$TMP/inc1.dispatch" >/dev/null 2>&1
[ "$(grep -c 'PRISM-INCLUDE-START' "$PKI")" = "1" ] \
  && ok "Include: re-run leaves exactly one managed region (idempotent)" || bad "Include: duplicate region on re-run"

# 3) glob spec resolves
PKI2="$TMP/inc2.md"; make_packet "$PKI2"
{ inc_dispatch "$PKI2" <<EOF
Include-Base: $INCD
Include: @*.md

Type: subagent
Lens: Simplicity
Lens-Desc: weigh fewest moving parts
EOF
} > "$TMP/inc2.dispatch"
expect_ok "Include: glob spec resolves" "$LAUNCH" prepare --dispatch "$TMP/inc2.dispatch"

# 4) mutual exclusion with Reference:
PKI3="$TMP/inc3.md"; make_packet "$PKI3"
{ inc_dispatch "$PKI3" <<EOF
Include: $INCD/a.md
Reference: $INCD/b.md

Type: subagent
Lens: Simplicity
Lens-Desc: d
EOF
} > "$TMP/inc3.dispatch"
expect_err "Include: + Reference: is rejected" "$LAUNCH" prepare --dispatch "$TMP/inc3.dispatch"

# 5) mutual exclusion with a hand-written ### Reference Materials
PKI4="$TMP/inc4.md"
cat > "$PKI4" <<EOF
## Full Question
q
## Context
c
### Reference Materials
- $INCD/a.md
## Constraints
You are a read-only leaf node.
EOF
{ inc_dispatch "$PKI4" <<EOF
Include: $INCD/b.md

Type: subagent
Lens: Simplicity
Lens-Desc: d
EOF
} > "$TMP/inc4.dispatch"
expect_err "Include: + hand-written ### Reference Materials is rejected" "$LAUNCH" prepare --dispatch "$TMP/inc4.dispatch"

# 6) missing file fails closed
PKI5="$TMP/inc5.md"; make_packet "$PKI5"
{ inc_dispatch "$PKI5" <<EOF
Include: $INCD/nope.md

Type: subagent
Lens: Simplicity
Lens-Desc: d
EOF
} > "$TMP/inc5.dispatch"
expect_err "Include: missing file fails closed" "$LAUNCH" prepare --dispatch "$TMP/inc5.dispatch"

# 7) secret refused by default, included under FILECTX_SECRETS=warn
PKI6="$TMP/inc6.md"; make_packet "$PKI6"
{ inc_dispatch "$PKI6" <<EOF
Include: $INCD/.env

Type: subagent
Lens: Simplicity
Lens-Desc: d
EOF
} > "$TMP/inc6.dispatch"
expect_err "Include: secret file refused by default" "$LAUNCH" prepare --dispatch "$TMP/inc6.dispatch"
expect_ok "Include: FILECTX_SECRETS=warn includes the secret" env FILECTX_SECRETS=warn "$LAUNCH" prepare --dispatch "$TMP/inc6.dispatch"

# 8) gpt-pro lens inlines the included file contents
PKI7="$TMP/inc7.md"; make_packet "$PKI7"
{ inc_dispatch "$PKI7" <<EOF
Include: $INCD/a.md

Type: gpt-pro
Lens: Deep
Lens-Desc: d
Posture: deep-reasoning
EOF
} > "$TMP/inc7.dispatch"
expect_ok "Include: prepares with a gpt-pro lens" "$LAUNCH" prepare --dispatch "$TMP/inc7.dispatch"
grep -q 'alpha contents' "$TMP/inc7-gpt-pro-deep.md" \
  && ok "Include: gpt-pro launcher inlines the included file contents" || bad "Include: gpt-pro launcher missing inlined contents"

# 8b) stale-region cleanup: an Include: run then a no-Include run on the SAME packet
# must leave NO orphaned managed region (else path-reading tiers read stale paths)
PKI8="$TMP/inc8.md"; make_packet "$PKI8"
{ inc_dispatch "$PKI8" <<EOF
Include: $INCD/a.md

Type: subagent
Lens: S
Lens-Desc: d
EOF
} > "$TMP/inc8a.dispatch"
"$LAUNCH" prepare --dispatch "$TMP/inc8a.dispatch" >/dev/null 2>&1
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "test"\n' "$PKI8"
  printf '\nType: subagent\nLens: S\nLens-Desc: d\n'; } > "$TMP/inc8b.dispatch"
"$LAUNCH" prepare --dispatch "$TMP/inc8b.dispatch" >/dev/null 2>&1
grep -q 'PRISM-INCLUDE-START' "$PKI8" \
  && bad "stale Include region survives a no-Include re-run on the same packet" \
  || ok "stale Include region is cleared on a no-Include re-run (same packet)"

# 8c) LARGE-packet mutual exclusion (regression: the sed|grep -q conflict check was
# fail-OPEN under pipefail+SIGPIPE on a big packet — must still reject Include+manual RM)
PKIL="$TMP/incL.md"
{ printf '## Full Question\nq\n## Context\nc\n### Reference Materials\n- %s\n' "$INCD/a.md"
  head -c 200000 /dev/zero | tr '\0' x
  printf '\n## Constraints\nYou are a read-only leaf node.\n'; } > "$PKIL"
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "test"\n' "$PKIL"
  printf 'Include: %s\n\nType: subagent\nLens: S\nLens-Desc: d\n' "$INCD/b.md"; } > "$TMP/incL.dispatch"
expect_err "Include: + manual ### Reference Materials rejected even on a large packet" \
  "$LAUNCH" prepare --dispatch "$TMP/incL.dispatch"

# 8d) malformed managed region (START with no END) must fail closed, not truncate
PKIM="$TMP/incM.md"
printf '## Full Question\nq\n## Context\nc\n<!-- PRISM-INCLUDE-START -->\n### Reference Materials\n- x\n## Constraints\nYou are a read-only leaf node.\n' > "$PKIM"
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\nPartial-User-Quote: "test"\n' "$PKIM"
  printf '\nType: subagent\nLens: S\nLens-Desc: d\n'; } > "$TMP/incM.dispatch"
expect_err "malformed Include sentinel (START, no END) fails closed (no truncation)" \
  "$LAUNCH" prepare --dispatch "$TMP/incM.dispatch"

# 9) scaffold emits the Include awareness stub (capture first — grep -q + pipefail
# would SIGPIPE the producer and false-fail the pipeline)
scaffold_out=$("$LAUNCH" scaffold --n 1 2>/dev/null)
case "$scaffold_out" in
  *$'\n# Include: '*) ok "scaffold emits the Include: awareness stub" ;;
  *) bad "scaffold missing Include: stub" ;;
esac

echo "== scaffold + prepare: no-subagents variant =="
PKTN="$TMP/prism-nosub.md"; make_packet "$PKTN"

# scaffold --no-subagents: partial + Variant header, zero subagent records, parallax fan kept
NS_OUT=$("$LAUNCH" scaffold --no-subagents --preset review 2>/dev/null)
case "$NS_OUT" in *$'\nVariant: no-subagents\n'*) ok "scaffold --no-subagents emits Variant: no-subagents" ;; *) bad "scaffold --no-subagents Variant header" ;; esac
case "$NS_OUT" in *'Prism-Mode: partial'*) ok "scaffold --no-subagents emits Prism-Mode: partial" ;; *) bad "scaffold --no-subagents partial mode" ;; esac
[ "$(printf '%s\n' "$NS_OUT" | grep -c '^Type: subagent$')" = "0" ] && ok "scaffold --no-subagents emits zero subagent records" || bad "scaffold --no-subagents zero subagent"
[ "$(printf '%s\n' "$NS_OUT" | grep -c '^Type: parallax$')" -ge 7 ] && ok "scaffold --no-subagents keeps the parallax fan" || bad "scaffold --no-subagents parallax fan"
# heaviest (subagent-slot) lens moves onto codex (review preset slot-0 = Adversarial)
printf '%s\n' "$NS_OUT" | grep -A1 '^To: codex$' | grep -q 'Lens: Adversarial' && ok "scaffold --no-subagents moves heaviest lens onto codex (xhigh)" || bad "scaffold --no-subagents codex lens shift"

# --n 0 with --no-subagents is rejected (that's the gpt-pro-only shape, not no-subagents)
expect_err "scaffold --no-subagents --n 0 rejected" "$LAUNCH" scaffold --no-subagents --n 0
# --out --no-subagents without a quote is rejected (it would be a FILL file → wasted Read)
expect_err "scaffold --out --no-subagents needs --partial-user-quote" "$LAUNCH" scaffold --no-subagents --preset review --packet "$PKTN" --out "$TMP/nsx.dispatch"

# happy path: scaffold a real no-subagents dispatch, prepare it, inspect the manifest
NSD="$TMP/prism-nosub.dispatch"
"$LAUNCH" scaffold --no-subagents --preset review --packet "$PKTN" --out "$NSD" --partial-user-quote "no subagents" >/dev/null 2>&1
expect_ok "prepare accepts a valid no-subagents dispatch" "$LAUNCH" prepare --dispatch "$NSD"
MANN="$TMP/prism-nosub-manifest.json"
[ "$(jq -r '.shape.variant' "$MANN" 2>/dev/null)" = "no-subagents" ] && ok "manifest .shape.variant = no-subagents" || bad "manifest variant"
[ "$(jq -r '.shape.mode' "$MANN" 2>/dev/null)" = "partial" ] && ok "manifest .shape.mode stays partial (minimal consumer fork)" || bad "manifest mode"
[ "$(jq -r '.shape.validated_roster' "$MANN" 2>/dev/null)" = "true" ] && ok "no-subagents roster is floor-checked (validated_roster true)" || bad "validated_roster"
[ "$(jq -r '.counts.subagents' "$MANN" 2>/dev/null)" = "0" ] && ok "manifest counts.subagents = 0" || bad "counts.subagents"
[ "$(jq -r '.shape.n' "$MANN" 2>/dev/null)" = "1" ] && ok "manifest .shape.n retained (drives the floor check)" || bad "shape.n retained"
jq -e '.shape.excluded_tiers | index("subagents")' "$MANN" >/dev/null 2>&1 && ok "manifest excluded_tiers includes subagents" || bad "excluded_tiers"

# floor check FAILS when a parallax tier is missing (the guarantee the variant adds over bare partial)
NSMISS="$TMP/nsmiss.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: partial\nVariant: no-subagents\nPrism-N: 1\nPartial-User-Quote: "no subagents"\n\nType: parallax\nTo: codex\nLens: Adversarial\nLens-Desc: d\n' "$PKTN" > "$NSMISS"
expect_err "no-subagents floor check fails on a missing parallax tier" "$LAUNCH" prepare --dispatch "$NSMISS"

# a smuggled subagent record under the variant is rejected
NSSUB="$TMP/nssub.dispatch"; cp "$NSD" "$NSSUB"; printf '\nType: subagent\nLens: SneakySub\nLens-Desc: should be rejected\n' >> "$NSSUB"
expect_err "no-subagents rejects a smuggled subagent record" "$LAUNCH" prepare --dispatch "$NSSUB"

# missing quote rejected (still a user-authorized reduced roster)
NSNOQ="$TMP/nsnoq.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: partial\nVariant: no-subagents\nPrism-N: 1\n\nType: parallax\nTo: codex\nLens: A\nLens-Desc: d\n' "$PKTN" > "$NSNOQ"
expect_err "no-subagents without a Partial-User-Quote rejected" "$LAUNCH" prepare --dispatch "$NSNOQ"

# Variant on Prism-Mode: full rejected
NSVF="$TMP/nsvf.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: full\nVariant: no-subagents\nPrism-N: 1\n' "$PKTN" > "$NSVF"
expect_err "Variant on Prism-Mode: full rejected" "$LAUNCH" prepare --dispatch "$NSVF"

# unknown Variant rejected
NSUV="$TMP/nsuv.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: partial\nVariant: bananas\nPrism-N: 1\nPartial-User-Quote: "x"\n\nType: parallax\nTo: codex\nLens: A\nLens-Desc: d\n' "$PKTN" > "$NSUV"
expect_err "unknown Variant rejected" "$LAUNCH" prepare --dispatch "$NSUV"

# back-compat: a bare partial (no Variant) carrying Prism-N is STILL rejected
NSBP="$TMP/nsbp.dispatch"
printf 'Shared-Packet: %s\nPrism-Mode: partial\nPrism-N: 1\nPartial-User-Quote: "x"\n\nType: parallax\nTo: codex\nLens: A\nLens-Desc: d\n' "$PKTN" > "$NSBP"
expect_err "bare partial with Prism-N still rejected (variant-free path unchanged)" "$LAUNCH" prepare --dispatch "$NSBP"

echo "== no-subagents variant: review fixes (N>1, M>0, --config, alias, calm) =="

# N=2 floor check passes; manifest records 14 parallax + shape.n=2 (preset is N=1 only → hand-build)
PKN2="$TMP/nsn2.md"; make_packet "$PKN2"; NSN2="$TMP/nsn2.dispatch"
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\nVariant: no-subagents\nPrism-N: 2\nPartial-User-Quote: "no subagents"\n' "$PKN2"
  i=0; for p in codex grok-build grok-composer glm kimi deepseek mimo; do for c in a b; do i=$((i+1)); printf '\nType: parallax\nTo: %s\nLens: L%s\nLens-Desc: d\n' "$p" "$i"; done; done; } > "$NSN2"
expect_ok "no-subagents N=2 floor check passes (14 parallax)" "$LAUNCH" prepare --dispatch "$NSN2"
[ "$(jq -r '.counts.parallax_total' "$TMP/nsn2-manifest.json" 2>/dev/null)" = "14" ] && ok "no-subagents N=2 manifest parallax_total=14" || bad "N=2 parallax_total"
[ "$(jq -r '.shape.n' "$TMP/nsn2-manifest.json" 2>/dev/null)" = "2" ] && ok "no-subagents N=2 shape.n=2" || bad "N=2 shape.n"

# M=1 happy path: gpt-pro asserted; manifest counts."gpt-pro"=1 + shape.m=1
PKM1="$TMP/nsm1.md"; make_packet "$PKM1"; NSM1="$TMP/nsm1.dispatch"
"$LAUNCH" scaffold --no-subagents --preset review --m 1 --packet "$PKM1" --out "$NSM1" --partial-user-quote "no subagents" >/dev/null 2>&1
expect_ok "no-subagents --m 1 prepares" "$LAUNCH" prepare --dispatch "$NSM1"
[ "$(jq -r '.counts."gpt-pro"' "$TMP/nsm1-manifest.json" 2>/dev/null)" = "1" ] && ok "no-subagents M=1 manifest gpt-pro=1" || bad "M=1 gpt-pro"
[ "$(jq -r '.shape.m' "$TMP/nsm1-manifest.json" 2>/dev/null)" = "1" ] && ok "no-subagents M=1 shape.m=1" || bad "M=1 shape.m"

# M=1 declared but zero gpt-pro records → variant floor check fails
NSM1B="$TMP/nsm1b.dispatch"
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\nVariant: no-subagents\nPrism-N: 1\nPrism-M: 1\nPartial-User-Quote: "x"\n' "$PKM1"
  for p in codex grok-build grok-composer glm kimi deepseek mimo; do printf '\nType: parallax\nTo: %s\nLens: LB-%s\nLens-Desc: d\n' "$p" "$p"; done; } > "$NSM1B"
expect_err "no-subagents M=1 with zero gpt-pro records fails floor check" "$LAUNCH" prepare --dispatch "$NSM1B"

# --no-subagent (singular) alias behaves identically
NS_SING=$("$LAUNCH" scaffold --no-subagent --preset review 2>/dev/null)
case "$NS_SING" in *$'\nVariant: no-subagents\n'*) ok "scaffold --no-subagent (singular) alias works" ;; *) bad "--no-subagent alias" ;; esac

# scaffold --partial-user-quote WITHOUT --no-subagents is rejected (no silent discard)
expect_err "scaffold --partial-user-quote without --no-subagents rejected" "$LAUNCH" scaffold --partial-user-quote "x" --preset review

# leftover scaffold FILL placeholder quote is rejected by prepare
PKF="$TMP/nsf.md"; make_packet "$PKF"; NSF="$TMP/nsf.dispatch"
{ printf 'Shared-Packet: %s\nPrism-Mode: partial\nVariant: no-subagents\nPrism-N: 1\nPartial-User-Quote: "FILL — the user'"'"'s exact words"\n' "$PKF"
  for p in codex grok-build grok-composer glm kimi deepseek mimo; do printf '\nType: parallax\nTo: %s\nLens: LF-%s\nLens-Desc: d\n' "$p" "$p"; done; } > "$NSF"
expect_err "no-subagents leftover FILL placeholder quote rejected" "$LAUNCH" prepare --dispatch "$NSF"

# calm informational line on the variant; the loud ⚠ PARTIAL must NOT appear
NSCALM=$("$LAUNCH" prepare --dispatch "$NSD" 2>&1 >/dev/null)
case "$NSCALM" in *"no-subagents run"*) ok "variant prepare prints the calm no-subagents line" ;; *) bad "variant calm line" ;; esac
case "$NSCALM" in *"PARTIAL"*) bad "variant must NOT print ⚠ PARTIAL" ;; *) ok "variant suppresses the loud ⚠ PARTIAL" ;; esac

# --config raw path: a valid no-subagents .shape with omitted m prepares + normalizes m→0
PKC="$TMP/nsc.md"; make_packet "$PKC"; CFGNS="$TMP/cfgns.json"
jq -n --arg p "$PKC" '{shared_packet:$p,
  parallax:[ ["codex","grok-build","grok-composer","glm","kimi","deepseek","mimo"][] | {to:., name:("ns-"+.), lens:("L-"+.), lens_desc:"d"} ],
  subagents:[],
  shape:{mode:"partial", variant:"no-subagents", n:1, partial_user_quote:"no subagents"}}' > "$CFGNS"
expect_ok "--config no-subagents variant (omitted m) prepares" "$LAUNCH" prepare --config "$CFGNS"
[ "$(jq -r '.shape.m' "$TMP/nsc-manifest.json" 2>/dev/null)" = "0" ] && ok "--config no-subagents omitted m normalized to 0" || bad "--config m normalized"

# --config raw path: variant on mode:full is rejected by the schema validator
PKCF="$TMP/nscf.md"; make_packet "$PKCF"; CFGFV="$TMP/cfgfv.json"
jq -n --arg p "$PKCF" '{shared_packet:$p, parallax:[], subagents:[{lens:"S",lens_desc:"d"}],
  shape:{mode:"full", variant:"no-subagents", n:1}}' > "$CFGFV"
expect_err "--config rejects variant on mode:full (schema)" "$LAUNCH" prepare --config "$CFGFV"

# --config raw path: omitted m normalized to 0 → a stray gpt-pro record is caught by the floor check
PKCG="$TMP/nscg.md"; make_packet "$PKCG"; CFGNSG="$TMP/cfgnsg.json"
jq -n --arg p "$PKCG" '{shared_packet:$p,
  parallax:[ ["codex","grok-build","grok-composer","glm","kimi","deepseek","mimo"][] | {to:., name:("ng-"+.), lens:("L-"+.), lens_desc:"d"} ],
  subagents:[], "gpt-pro":[{lens:"G", lens_desc:"d"}],
  shape:{mode:"partial", variant:"no-subagents", n:1, partial_user_quote:"x"}}' > "$CFGNSG"
expect_err "--config no-subagents omitted m + stray gpt-pro caught by floor check" "$LAUNCH" prepare --config "$CFGNSG"

echo
echo "==== $pass passed, $fail failed ===="
[ "$fail" -eq 0 ]
