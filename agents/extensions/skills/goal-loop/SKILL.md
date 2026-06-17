---
name: goal-loop
description: |
  Drive a goal through review→fix iteration by composing goal-elicit, goal-drive, and multi-model
  review (prism, Claude-only). A thin, modeless, stepped loop — one phase per invocation
  (elicit → spec-review → drive → review → you pick which fixes apply → fix → re-review) — with state on
  disk so it resumes after interruption or compaction. It auto-handles the ~83% of out-of-scope/unmapped
  findings (you never see them) and surfaces only the small actionable batch to confirm — never
  blind-applies (unsafe). Use for "loop this to done with review", "close the review-fix loop",
  "goal-loop". Review needs Claude (prism), degrades off-Claude. Interactive by default; **`--auto`** runs
  it unattended/headless under Claude Code's native `/goal` — both gates become fail-closed policies
  (oracle-gated safe-subset auto-fix + a deferred morning queue), never blind-apply. Does NOT interview
  (that's goal-elicit). Skip for one-off edits and lone reviews.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill, AskUserQuestion
---

# goal-loop

A thin, **modeless** orchestrator that closes the loop the three existing skills leave open:
[[goal-elicit]] writes a verifiable artifact and stops; [[goal-drive]] drives it to verified done;
[[prism]] reviews from many models. goal-loop sequences `elicit → [spec-review] → drive → review →
fix → re-review` and owns the **one thing none of the three can**: the **loop edge** — turning review
findings into the *next* drivable unit, gated by you. It composes the three skills; it never modifies,
re-implements, or absorbs them.

> **Two modes.** *Interactive (default):* both human gates (spec sign-off, fix classification) call
> `AskUserQuestion` and need a live operator. *Autonomous (`--auto`):* for headless/unattended runs under
> the native `/goal` command, where a blocking `AskUserQuestion` would deadlock the turn (the `/goal`
> evaluator fires only **after** a turn finishes). `--auto` replaces both gates with fail-closed policies,
> auto-fixes only the frozen-oracle-RED subset, and defers everything needing scope judgment to a morning
> report — see **§ Autonomous mode (`--auto`)** and `references/loop-protocol.md` § Autonomous mode.

## Two non-negotiables (the design hinges on these)

1. **You decide which findings become fixes — goal-loop never blind-applies them.** This is not
   caution; it's measured. On a real run only ~17% of review findings mapped cleanly to an existing
   acceptance criterion; the rest were defects with no acceptance line, out-of-scope improvements, or
   scope calls only a human can make (a human out-scoped the *loudest* finding and vetoed a
   multi-reviewer refactor). Two harnesses confirm a mechanism can't safely auto-apply them:
   `scripts/empirical_gate.py` (a router false-applies F1/F16 — identifier-collision, semantic not
   lexical) and `scripts/oracle_gate.py` (verification-anchoring is safe but auto-applies ~nothing
   without strong pre-signed oracles). So goal-loop **routes** mechanically and **proposes**; you
   classify the actionable batch. The path to real auto-apply is oracle-gating — see *Report-only*.
2. **The original goal artifact is binding authority.** Every accepted fix maps to an existing
   acceptance / `done_when` / constraint, or a new acceptance line you author. A real defect with **no**
   acceptance line (`in_scope-unmapped`) is **surfaced in the actionable batch** — to accept it you
   author the new acceptance line first; out-of-scope and `could` findings are **deferred** to the loop
   ledger (never written into the source artifact); scope changes require explicit promotion. (The one
   exception is the `spec-review` phase, which edits the artifact *before* it locks; once you sign off,
   it's frozen.)

## Modeless & stepped — one phase per invocation

The **artifact + the loop ledger on disk are the state**; "continue" means "advance the next phase the
ledger says is unfinished." Each invocation advances **exactly one phase** — `elicit`, `spec-review`,
`drive`, `review`, `classify`, or `fix` — persists `current_phase`, and **stops**. It does **not**
chain phases. That's deliberate: a long inline run triggers auto-compaction, which can drop the
orchestration instructions; because state lives on disk, re-invoking re-reads this file and the ledger
says exactly where you are. Resume the way goal-drive resumes — reconcile against the repo, trust
verified facts. No Stop hook, no plugin, no humanize coupling: it's a portable skill.

**Read `references/loop-protocol.md` in full before entering any phase** — it is the authoritative
source for the ledger schema, the exact router procedure, normalization, crash-safety write ordering,
the review-packet template, and the per-backend resume contracts; the tables here are summaries only.

**The two human gates** (spec-review sign-off, classify disposition) each contain **exactly one user
interaction** and remain the active phase until the answer is captured: render the choices, call
`AskUserQuestion`, and only **after** the reply write the durable artifacts (spec edits + `spec_approved`,
or the disposition + `fix-rN.checklist.json`) and then advance `current_phase`. If re-entered before the
reply (interrupted/compacted), re-present the same batch — never advance or write a fix on a partial
disposition.

## Runtime portability & the review backend

Portable; **never detects its runtime**. Only the *review backend* is Claude-specific, and it's pluggable:
- `--review prism` (default) — multi-model review (Claude-only). Resolved by **capability, not runtime**:
  if the prism skill is unavailable or refuses (off-Claude), goal-loop writes
  `.goals/<id>.review-rN.request.md` and stops (`review_backend_unavailable`).
- `--review external` — write the review packet and stop; you review elsewhere, place the synthesis,
  and `continue` resumes at classify.
- `--review local` — single-agent skeptical self-review in-session; portable, weaker.
- `--review none` — elicit + drive only; `GOAL-LOOP COMPLETE` after the drive marker, no loop.

## Spec-review (mod #1 — on by default)

**Runs by default** (config `1 m`): before driving, review the **goal spec itself** — acceptance
criteria testable/complete? gaps, contradictions, untestable `done_when`, likely findings that won't map
later? You approve/edit the strengthened spec (the one pre-lock edit point), which then **freezes as the
binding authority**. Spec quality is the single biggest lever — it raises the actionable fraction *and*
is the path toward safe auto-apply — so it is the default, not opt-in. **`--no-spec-review` skips it**,
and goal-loop **auto-skips for a Clear-domain artifact** (a one-shot contract goal-elicit fast-laned —
no review tax on trivial goals). Override the depth with `--spec-review "<config>"`. On **reject** at
sign-off → `GOAL-LOOP STOPPED` (`spec_rejected`); re-run goal-elicit. Details:
`references/loop-protocol.md` § Spec review.

## Autonomous mode (`--auto`)

`--auto` runs the loop **unattended** under Claude Code's native `/goal`. The `/goal` evaluator fires only
**after a turn finishes** and is **tool-less**, so a blocking `AskUserQuestion` deadlocks the turn — `--auto`
therefore replaces **both** human gates with **fail-closed autonomous policies** and terminates on **printed
markers**. It changes only gate behavior, termination, and handoff; it composes the same three skills. **It
is strictly more conservative than interactive mode, never less.** Authoritative mechanism (policy table,
markers, morning report, hardening): `references/loop-protocol.md` § Autonomous mode — read it before an
`--auto` run.

- **Gate A** → spec-review runs **report-only**; the elicited spec is **frozen as-is** (never auto-edited);
  proposed new ACs/gaps go to the morning report. `--no-spec-review` skips the pass.
- **Gate B** → deterministic auto-disposition: **AUTO-FIX only** the `in_scope-mapped` finding whose **frozen
  oracle is currently RED** (the exact `oracle_gate.py` gate: RED→GREEN + suite GREEN + paths ⊆ authority +
  no test/spec/oracle edit + behavioral-delta contained). **Everything else DEFERS** to a morning queue
  (`in_scope-unmapped`, mapped-no-oracle, `could`, out-of-scope, `needs_user`); one-way-door / oscillation /
  normalization-failure **STOP-HALT**. **Cross-model consensus may prioritize the queue, never authorize a
  fix.** No new acceptance line is ever auto-authored (that's scope mutation, invariant #2).
- **Honest value:** *drive → review → safe-subset auto-fix → a tight pre-classified morning decision queue* —
  **not** the operator's scope judgment. Oracle coverage is ~empty by default, so a first run typically
  **auto-fixes nothing** and just produces the queue. That is correct, not a failure — the report says so.
- **Terminate** with one of `GOAL-LOOP AUTO-COMPLETE: <id>` (nothing left for you), `GOAL-LOOP AUTO-HANDOFF:
  <id>` (converged, queue awaits — the common case), or `GOAL-LOOP AUTO-HALTED: <id> — <reason>`, each
  preceded by an evidence block. The morning report is `.goals/<id>.auto-report.md`.
- **Portability:** off-Claude / no review backend ⇒ **no auto-fix** (drive + verify only, defer all); never
  fakes cross-model review, never auto-accepts single-model output.
- **Oracles + hardening:** the auto-fixable RED oracles come from a frozen `.goals/<id>.oracles.json` manifest
  the operator authors **at sign-off** (validate/run via `scripts/oracle_manifest.py`); no manifest ⇒ nothing
  auto-fixes (review + queue only). Optional opt-in for high-stakes runs: `--worktree` isolation and a
  deterministic completion Stop-hook — `references/loop-protocol.md` § Optional hardening.

## What it produces

- `.goals/<id>.loop.json` — an **index-only** ledger (round, phase, prism config, artifact paths,
  review/findings paths, dispositions, `round_start_ref`, stop reason). Schema: `references/loop-protocol.md`.
- `.goals/<id>.spec-review.md` — the spec-review synthesis (unless `--no-spec-review` / Clear-domain).
- `.goals/<id>.review-rN.md` / `.review-rN.findings.json` — the review synthesis + normalized findings.
- `.goals/<id>.oracles.json` — (optional) the **frozen-oracle manifest** authored at sign-off; what `--auto`
  consults to find auto-fixable RED oracles. Schema + use: `references/loop-protocol.md` § The frozen-oracle manifest.
- `.goals/<id>.auto-report.md` — (under `--auto`) the morning report: outcome, auto-applied fixes, and the
  pre-classified decision queue. Written before the terminal marker.
- `.goals/<id>.fix-rN.checklist.json` — a child fix artifact per round, built from the findings **you
  accepted**. The source artifact stays immutable; findings never patch it.

## Invocation

```
/goal-loop [--auto] [--prism "<config>"] [--no-spec-review | --spec-review "<config>"]
           [--review prism|external|local|none] [--max-rounds N] [--artifact <path>] -- <request>
/goal-loop continue [<id>]
```

- `--auto` — **unattended mode** (see § Autonomous mode): both human gates become fail-closed policies, no
  `AskUserQuestion`, terminates on the `AUTO-*` markers. Intended to run under the native `/goal` command.
  Because it cannot ask, `--auto` **requires** `--prism` (or inherits the ledger's `prism_config`); if both
  are absent it defaults the review depth to `2 m` rather than blocking.
- `--prism "<config>"` — forwarded **verbatim** to prism (`2 m`, `2 m +2 gp`, …). Omitted (interactive) →
  goal-loop asks at the review gate; omitted under `--auto` → defaults to `2 m` (above).
- `--max-rounds N` — review/fix cycles (default **2**; loops oscillate). `continue --max-rounds <N>` extends.
- `--no-spec-review` / `--spec-review "<config>"` — skip the (default-on) spec review, or override its
  depth. (Auto-skipped for a Clear-domain one-shot artifact.)
- `--artifact <path>` — start from an existing artifact (skip elicit). `continue [<id>]` resumes the
  sole non-terminal `.loop.json` (lists candidates if more than one; if none, say so and offer to start one).

### Invocation mechanics

Invoke goal-elicit, goal-drive, and prism via the **Skill tool, inline in this owning session** —
never via Agent/Task/subagent. A `Skill`-invoked goal-drive is **inline and retains full edit
authority** (its leaf/read-only contract applies only when spawned as a subagent, which goal-loop
never does). Invoke `Skill(prism, "<config> <review packet>")` at top level; prism owns its own
read-only-leaf fan-out. Wait for the invoked skill's terminal marker before advancing the ledger.

## The loop

State = the source artifact + `.goals/<id>.loop.json`. **Advance exactly one phase per invocation,
persist the ledger, STOP.** On (re)entry, read `current_phase`, reconcile against the repo, run only it:

```
elicit    no ready artifact → goal-elicit (once). Stop after: ready → current_phase = spec-review
          (default; → drive directly if --no-spec-review or a Clear-domain one-shot artifact);
          draft/blocked → stopped.                                                         ← ends invocation
spec-rev  (default; skipped by --no-spec-review / Clear-domain) freeze a SPEC packet {objective ·
          acceptance/done_when · scope · constraints}; run the review backend; persist .spec-review.md;
          present findings; YOU approve/edit the spec (pre-lock); on sign-off freeze → current_phase=drive;
          on reject → stopped (spec_rejected). STOP.                                          [human gate]
drive     **record round_start_ref FIRST** (on entering drive — the diff baseline), then goal-drive
          (Skill, inline). On GOAL-DRIVE COMPLETE + verification → current_phase=review. On STOPPED →
          stopped. STOP.                                                                   ← ends invocation
review    if round > max_rounds → stopped (max_rounds), do not dispatch. Else if `prism_config` is empty,
          ask the user for it now; freeze the review packet {artifact · diff since round_start_ref ·
          COMPLETE marker · verification}; run the backend; persist .review-rN.md, normalize →
          .findings.json, set current_phase=classify LAST. STOP.                            ← ends invocation
classify  the router mechanically **disposes the non-actionable bulk** (you never see it):
          out-of-scope/`could` → DEFER (ledger), needs_user/ambiguous/one-way-door/recurrence → HALT
          (GOAL-LOOP STOPPED). Only the remaining **actionable batch** (in_scope-mapped +
          in_scope-unmapped) is surfaced — a separate step. YOU disposition that batch via
          AskUserQuestion (accept/defer/reject per item; for an in_scope-unmapped accept, author the new
          acceptance line first). Capture the reply, write .fix-rN.checklist.json from accepted findings,
          THEN set current_phase=fix. `reject` → discard the round → review gate. STOP.    [human gate]
fix       **record round_start_ref FIRST** (on entering fix — the pre-patch baseline for the re-review),
          then goal-drive (Skill, inline) on .fix-rN.checklist.json. On COMPLETE → current_phase=review,
          round+1. STOP.                                                                   ← ends invocation
```

The **unit of iteration** is one review/fix round. The two human gates are the **spec sign-off /
artifact** and **review→fix** (classify); the per-phase STOPs keep any one invocation short enough to
survive compaction. The router shrinks the classify gate from "every finding" to "the small actionable
batch" — that's the ergonomic win over a raw per-finding gate, kept honest by leaving you the decision.

**Under `--auto`,** the same phase sequence runs, but `spec-rev` and `classify` execute the **autonomous
policies** instead of `AskUserQuestion` — spec-review is report-only (freeze elicited spec), and classify
auto-fixes only the oracle-RED subset while deferring/halting the rest — and the loop ends on an `AUTO-*`
marker. See **§ Autonomous mode** and `references/loop-protocol.md` § Autonomous mode.

## Composition wiring

| Phase | Skill | Dispatcher | Rail |
|---|---|---|---|
| Elicit | goal-elicit | goal-loop (once) | writes one artifact, stops, never re-invoked |
| Spec-review (opt) | prism | goal-loop, top-level | reviews the *spec*; you approve edits pre-lock; not re-elicitation |
| Implement / Fix | goal-drive | goal-loop, **Skill-inline** | inline retains edit authority (a subagent goal-drive would be a leaf and lose it) |
| Review | prism (default) | goal-loop, **top-level only** | Claude-only; prism owns its own read-only leaf dispatch |
| Review → fix | **goal-loop itself** | — | routes mechanically; **you** classify the actionable batch |

Rails goal-loop enforces on itself: never asks goal-drive to invoke prism; **never re-elicits** mid-loop
(if review shows the *goal* is wrong, stop and tell the user to re-run goal-elicit); top-level
user-invocable only.

## Review → fix (the router proposes; you decide)

After review, the router **mechanically** disposes the bulk so you don't have to: `out_of_scope` and
`could` → **DEFER** (recorded in the ledger, a suggested `## Emergent` line printed, source untouched);
`needs_user` / one-way-door / recurrence → **STOP**. It then prints a one-line **deferred/stop audit**
(counts by scope+severity + the titles of any deferred `blocker`/`should`, with `expand <id>` to read
one) so the bulk is auditable, not invisible, and surfaces only the remaining **actionable batch**
as a numbered list — each `{severity, claim, proposed fix, proposed acceptance, proposed verification,
nominated AC}` — and you reply `defaults`, `1a 2c …`, `reassign <id>→<AC>` (correct a wrong nomination),
`reject`, or `approve`. The router's `maps_to` is a **nominee, not an authority** — its lexical mapping
errs in both directions, so confirm or `reassign` it. **Nothing is written to a fix checklist until you `approve`.** Buckets, the finding schema, the normalization procedure, and the
fix-checklist template: `references/loop-protocol.md`.

## Stop / convergence / resumption

- **GOAL-LOOP COMPLETE** — the latest review surfaces no accepted `blocker`/`should` finding, every fix
  artifact is verified done, and the ledger points to the evidence. Echo the marker last. (If you
  `approve` a round with zero accepted but some *deferred*, ask whether to mark it clean → COMPLETE or
  return to review — don't assume done.)
- **GOAL-LOOP COMPLETE (no-review)** — with `--review none`, after the drive marker (no loop).
- **`--auto` markers** — under `--auto` the loop ends instead on `GOAL-LOOP AUTO-COMPLETE: <id>` (drive done,
  oracles GREEN, decision queue empty), `GOAL-LOOP AUTO-HANDOFF: <id>` (converged, a deferred queue awaits —
  the common case), or `GOAL-LOOP AUTO-HALTED: <id> — <reason>`, each preceded by an evidence block and
  paired with `.goals/<id>.auto-report.md`. Details + the `/goal` condition: `references/loop-protocol.md` § Autonomous mode.
- **GOAL-LOOP STOPPED** — with `stop_reason` ∈ {`goal_drive_stopped`, `review_backend_unavailable`,
  `needs_user`, `spec_rejected`, `review_rejected`, scope/authority-exceeded, one-way-door, `max_rounds`,
  `oscillation` (same finding recurs), `normalization_failed` (extraction incomplete/invalid),
  `findings_escalating` (each round surfaces more/higher-severity findings than the last — the work is
  regressing)} — under `--auto` the AUTO-HALTED set adds `stale_baseline`, `lock_conflict`,
  `unauthorized_path`, `spec_contradiction` (see `references/loop-protocol.md` § Termination). Print the
  marker first, then hand back.
- **Resume** — read `current_phase`, reconcile against verified artifacts + repo (files over the
  pointer; if `review-rN.findings.json` exists, skip re-review → classify). Crash-safety write order:
  `references/loop-protocol.md` § Crash safety.

## Report-only today — and the one upgrade path

**Interactive mode ships report-only** (route, auto-handle the ~83% DEFER/STOP, confirm only the small
actionable batch). The **only** fundamentally-safe way to remove that confirm is **oracle-gating, not a
smarter router** — verify each change against a *pre-signed, frozen executable oracle* (auto-actionable
only when its acceptance oracle is RED; apply only on RED→GREEN + no regression + anti-overfit; F1/F16
STOP by construction). **`--auto` is the opt-in that enables exactly this gate** (and nothing more):
unattended, it AUTO-FIXes only the oracle-RED subset and defers the rest to a morning queue. `oracle_gate.py`
PASSES (false-auto=0) but shows the covered subset is ~empty until you author stronger oracles at sign-off —
so `--auto` with no oracles auto-fixes nothing and is review-plus-queue, by design. Full mechanism + the
15-perspective verdicts: `references/loop-protocol.md` § Autonomous mode and § The path beyond report-only,
`~/.ai/reports/20260616-2243-goalloop-auto-design.md`, and `~/.ai/reports/20260612-2230-goal-loop-fundamental-verdict.md`.

## Single biggest risk

**Scope mutation through review-to-fix conversion** — under load a review always produces plausible
improvements; if they silently become work, the loop stops driving *your* goal and lets reviewers
redefine it. Defense is the two non-negotiables: you classify the actionable batch (nothing written
until `approve`) + binding-authority (fixes map to acceptance or you author it; out-of-scope never
touches the source), plus the round cap and oscillation guard.

## Must not

- Do not blind-apply review findings; route mechanically, surface the actionable batch, write nothing
  until the user `approve`s.
- **Under `--auto`:** never call `AskUserQuestion` (it deadlocks the `/goal` turn); never auto-edit or
  auto-strengthen the frozen spec, and never auto-author a new acceptance line (that is scope mutation);
  AUTO-FIX **only** the oracle-RED subset (DEFER/HALT everything else); cross-model consensus may reorder
  the morning queue but never authorize a fix; fail toward HALT, not toward applying.
- Do not let findings patch the **source** artifact (including out-of-scope `## Emergent`); record those
  in the ledger. Fixes land in child `fix-rN` artifacts.
- Do not chain phases; advance one phase per invocation, persist, stop. Do not re-elicit mid-loop or
  enter a "mode".
- Do not embed review inside goal-drive, ask goal-drive to dispatch prism, or spawn goal-drive as a
  subagent for the work.
- Do not fake cross-model review off Claude — degrade to `external`/`local`/`none` and say so.
- Do not push/deploy/one-way-door without explicit assent (inherit goal-drive's rail).

## Files in this skill

- `SKILL.md` — this file.
- `references/loop-protocol.md` — the `.loop.json` ledger schema, crash-safety, the finding schema +
  four-bucket classification, the normalization procedure, oscillation, the fix-checklist template, the
  spec-review front gate, the per-backend resume contracts, the review-packet template, and the
  oracle-gating upgrade path.
- `scripts/empirical_gate.py` — replays the roadmap review through a lexical router; **FAILS**
  (false-auto F1/F16) — the evidence that a router can't safely blind-apply.
- `scripts/oracle_gate.py` — replays it through oracle-gating; **PASSES** (false-auto=0) — the evidence
  that the safe auto-apply path is verification against pre-signed oracles, and that it covers ~nothing
  without strong oracles.
- `scripts/oracle_manifest.py` — the **live** frozen-oracle manifest validator + RED/GREEN evaluator that
  `--auto` consults (oracle_gate.py is the offline safety proof; this runs the operator's real oracles).
  `validate` / `evaluate` / `selftest`.
