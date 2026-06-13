# goal-loop — loop protocol (stepped, portable)

The mechanism behind [[goal-loop]]'s SKILL.md. goal-loop is a **thin, modeless, stepped** orchestrator:
one phase per invocation, state on disk, resume by reconciling. It **routes** review findings
mechanically and surfaces a small actionable batch for **you** to classify — it does not blind-apply.
This file pins the ledger, crash-safety, the router, the finding/fix schemas, the spec-review front
gate, the per-backend resume contracts, the review packet, and the oracle-gating upgrade path.

## Why the human classifies (the evidence)

On a real elicit→implement→prism-review→fix loop (the `roadmap` layer, 18 findings) only **~17% mapped
cleanly** to an existing acceptance criterion; ~50% were defects with **no acceptance line**, ~22%
out-of-scope, ~11% needed a human scope call. The two highest-value human acts — out-scoping the
*loudest* finding (a NO-SHIP bug that *predated* the layer) and **vetoing a 3-reviewer consensus
refactor** of correct code — are un-authorable in any spec. Two harnesses confirm no mechanism safely
blind-applies: `scripts/empirical_gate.py` (a lexical router false-applies F1/F16 — identifier
collision, semantic not lexical) and `scripts/oracle_gate.py` (verification-anchoring is safe but
auto-applies ~nothing without strong pre-signed oracles). So the router auto-handles the bulk and
**you decide the actionable batch**; the spec-review front gate shrinks that batch by raising spec quality.

## The loop ledger — `.goals/<id>.loop.json`

Index-only. It records *which* artifact was driven, *which* review ran, *what* you decided, and *where*
to resume. It **must not** duplicate per-unit execution state (goal-drive owns that on the artifact).

```json
{
  "schema_version": "goal-loop/v1",
  "id": "20260612-roadmap-acquisition-layer",
  "source_artifact": ".goals/20260612-roadmap-acquisition-layer.plan.md",
  "current_phase": "classify",          // elicit|spec-review|drive|review|classify|fix|done|stopped
  "round": 2,
  "max_rounds": 2,
  "review_backend": "prism",            // prism|external|local|none
  "prism_config": "2 m",                // forwarded verbatim; "" => prism auto-sizes
  "spec_approved": true,                // set at spec-review sign-off; the artifact is frozen after
  "round_start_ref": "a1b2c3d",         // git rev captured on entering drive/fix this round (diff baseline)
  "rounds": [
    { "round": 1, "round_start_ref": "0f9e8d7", "drive_marker": "GOAL-DRIVE COMPLETE: <id> — …",
      "review_report": ".goals/<id>.review-r1.md", "findings": ".goals/<id>.review-r1.findings.json",
      "fix_artifact": ".goals/<id>.fix-r1.checklist.json",
      "disposition": { "accepted": ["R1-F02"], "deferred": ["R1-F05","R1-F08"], "needs_user": [] },
      "status": "fix_done" }            // review_pending|awaiting_external_review|awaiting_user|fix_pending|fix_done|clean|stopped
  ],
  "stop_reason": null
}
```

`current_phase` is the authoritative loop pointer; round `status` is per-round detail; on any
disagreement (or vs. the files), **files win** (reconcile, don't trust the pointer). A reached cap is
`stopped` with `stop_reason: max_rounds`. Out-of-scope findings live only in the disposition/findings —
never in the source artifact.

## Crash safety — write order + durability table

Each phase persists its **durable artifacts first** and advances `current_phase` **last**, so a crash
leaves a recoverable state and resumption keys on *file existence*, not the pointer.

| Transition | Durable writes, in order | Resume rule mid-transition |
|---|---|---|
| elicit → drive/spec-review | source artifact; then ledger phase | artifact ready, phase still `elicit` → set next; draft/blocked → `stopped` |
| spec-review → drive | `spec-review.md` + applied edits; then `spec_approved` + freeze + phase | findings present but not approved → re-present; `spec_approved` set → drive |
| drive → review | goal-drive patches + marker; then `round_start_ref` + phase | marker present, phase `drive` → set `review` (goal-drive reconciles its units) |
| review → classify | `review-rN.md`; then `findings.json`; then phase | **findings file exists → skip to classify** (never re-dispatch review) |
| classify → fix | full `disposition` + `fix-rN.checklist.json`; then phase | partial/empty disposition → re-present the actionable batch; write nothing until `approve` |
| fix → review | goal-drive drives child checklist + marker; then phase + `round+1` | mid-fix crash → goal-drive's reconcile-from-artifact resumes |

## Spec review (mod #1)

**On by default**, between `elicit` and `drive` (config `1 m`); **skipped by `--no-spec-review` or for a
Clear-domain one-shot artifact** (goal-elicit's triage = Clear); override depth with `--spec-review
"<config>"`. It reviews the **goal artifact as a contract**, before any code, to strengthen the
acceptance criteria — and it is the one point the artifact may still change. It uses its own review
backend independent of `--review` (prism if available, else `local`); `--review none` suppresses only
the *implementation* review, not spec-review. On **reject** at sign-off → `GOAL-LOOP STOPPED`
(`stop_reason: spec_rejected`); re-run goal-elicit with a revised artifact.

Freeze a SPEC packet `{objective · acceptance_criteria/done_when · scope_in/out · constraints ·
authority · rollback}` (no diff, no code) and ask the backend a contract-quality question:

```
Review this goal specification as a CONTRACT, before implementation. Do NOT propose how to build it.
Flag only: untestable/missing-verification acceptance criteria; risks with no acceptance line (gaps);
contradictions between scope and the acceptance set; vague done_when; missing rollback/authority. For
each, propose the concrete acceptance line that closes it. Also name the implementation-review findings
you expect later that would NOT map to any current acceptance criterion — close those now.
```

Persist to `.goals/<id>.spec-review.md`. Present findings; **you** approve which acceptance lines to add.
goal-loop may `Edit` the artifact to apply them — permitted because the artifact is **pre-lock** (being
finalized, not yet binding) and it is **not re-elicitation** (no interview; goal-elicit is never
re-invoked). On sign-off, record `spec_approved` + a content hash; the artifact is **frozen** —
implementation review never patches it (invariant #2). Backend portability is the same as review.

## The router — nominator, not apply-authority

After review, the router **mechanically** disposes the bulk so you don't read it, and surfaces only the
actionable batch. It is a deterministic procedure (model self-classification was ~17% reliable):

```
for each finding (claim/proposed_fix), set scope mechanically:
   key-term overlap (nouns/verbs, stopwords removed) of claim vs each acceptance/done_when/constraint:
     exactly one ≥ threshold → in_scope-mapped, maps_to = that AC id
     zero                    → in_scope-unmapped
     two+ (ambiguous)        → needs_user            # fail closed — never guess
   severity == could                                → out_of_scope
   recurrence (same maps_to OR ≥50% claim-overlap with an accepted+fixed prior finding) → needs_user
   proposed_fix ∉ authority.allow_paths             → needs_user
   one-way-door keywords (delete|drop|migrate|deploy|publish) → needs_user

auto-dispose (you never see these):
   out_of_scope → DEFER (ledger; print a suggested `## Emergent` line; source untouched)
   needs_user   → STOP (surface the reason; the loop halts for you)
surface the ACTIONABLE batch (in_scope-mapped + in_scope-unmapped) for your decision:
   you bucket each → accepted (a fix item) | deferred | rejected;
   in_scope-unmapped accepted ⇒ you author the new acceptance line first.
nothing is written to fix-rN.checklist.json until you `approve` the batch.
```

Severity does **not** decide actionability: the roadmap's loud NO-SHIP finding had no AC → STOP, not
fix; the consensus refactor of correct code → out-of-scope → DEFER. The router fails the way the human
did. It **nominates** `maps_to`; it is never the apply authority (see *The path beyond report-only*).

## The finding schema — `.goals/<id>.review-rN.findings.json`

```json
{ "id": "R01-F03", "source_review": ".goals/<id>.review-r1.md#finding-3", "severity": "blocker|should|could",
  "claim": "...", "proposed_fix": "...", "proposed_acceptance": "...",
  "proposed_verification": "command | test | observable", "review_backend": "prism|external|local",
  "scope": null, "maps_to": null, "status": "pending" }
```

The router fills `scope`/`maps_to` mechanically; **you** set the final disposition on the surfaced batch.
When `review_backend == local` (single-model, no cross-model independence), flag it at the classify gate
("⚠ single-model review — verify before accepting") and bias borderline items toward `needs_user`.

### Normalization procedure (prism synthesis → findings.json)

prism returns verdict-led prose. Producing the findings file is a **one-time LLM extraction step** (the
router and classify gate are mechanical only *afterward*): read `review-rN.md`; extract distinct
actionable findings, **dedupe by claim**; assign ids `R{N}-F{nn}`; fill severity / claim / proposed_fix
/ proposed_acceptance / proposed_verification; leave scope/maps_to/status for the router + you; write
`findings.json`; advance `current_phase=classify`.

### Oscillation rule

A round-N finding **recurs** if its `maps_to` equals that of an accepted+fixed finding from **any prior
round**, or its `claim` shares ≥50% key terms with one. Compute at classify time by scanning all prior
`findings.json`. On recurrence → `stop_reason: oscillation`, do not write the fix, emit `GOAL-LOOP STOPPED`.

## The child fix artifact — `.goals/<id>.fix-rN.checklist.json`

A conforming goal-drive bring-your-own checklist (must pass `goal-drive/scripts/lint_goal_artifact.py`).
One item per accepted finding; the source artifact is never patched.

```json
{ "schema_version": "goal-checklist/v1", "id": "<id>-fix-r1",
  "objective": "Apply accepted review fixes for <id> (round 1).",
  "source_artifact": "<frozen artifact path>",
  "authority": { "allow_paths": ["…from the artifact…"], "allow_commands": ["…"] },
  "commit_policy": "per_unit", "batch_size": 1,
  "done_when": ["every item below is state:done with evidence"],
  "items": [
    { "id": "R1-F02", "maps_to": "AC-3", "source_review": ".goals/<id>.review-r1.md#finding-2",
      "action": "warn + preserve evidence when `method set` targets the current id",
      "acceptance": "set to current id keeps stage+evidence; RED→GREEN test passes",
      "verification": "pytest test_set_same", "state": "pending" } ]
}
```

## Backends — output + resume contract per `--review`

| Backend | This invocation writes | `continue` resumes by |
|---|---|---|
| `prism` (default, Claude) | `Skill(prism, "<config> <packet>")` → `review-rN.md` → normalize → `findings.json` → classify | the review→classify rule above |
| `external` | `review-rN.request.md` (frozen packet); `awaiting_external_review`; stop | you place the synthesis at `review-rN.md`; `continue` normalizes → classify (absent → stop, tell you where) |
| `local` | in-session skeptical self-review → `review-rN.md` + `findings.json` | as `prism`. No cross-model independence — bias toward `needs_user` |
| `none` | nothing (no review scheduled) | n/a — `GOAL-LOOP COMPLETE` after the drive marker |

## The frozen review packet

Build once per round; hand to the backend unchanged (also what `--review external` writes). Feed
**evidence, not narrative** — this preserves reviewer independence when drive ran in the same session:

```
## Review request — goal <id>, round <N>
Review this implementation against its source goal artifact. Return actionable findings only if they
violate an acceptance criterion, done_when item, constraint, or verification integrity. Classify
anything else as optional or out-of-scope. For each: severity, the specific claim, a bounded fix, an
acceptance criterion, and how to verify it.
### Source artifact
<path + the acceptance_criteria / done_when / constraints block, verbatim>
### What changed
<git diff --stat since round_start_ref, + changed file list>
### Verification evidence
<the GOAL-DRIVE COMPLETE marker line + the real verification output it printed>
```

For `--review prism`, forward `prism_config` verbatim ahead of the packet (`Skill(prism, "2 m <packet>")`).

## The path beyond report-only — oracle-gating (the future opt-in)

goal-loop ships with the human classifying the actionable batch (above). The **only fundamentally-safe
way to remove that step** is not a better router or a judge — it's verification against pre-signed
oracles (15-perspective verdict: `~/.ai/reports/20260612-2230-goal-loop-fundamental-verdict.md`;
`scripts/oracle_gate.py` PASSES with false-auto=0):

- At sign-off, every mechanically-checkable acceptance criterion compiles to a **frozen**
  `{ac_id, oracle_id, command, allowed_paths, preservation}` record (non-mechanical → `oracle: manual`).
  The roadmap plan's executable `Acceptance:` blocks are exactly these oracles.
- A finding is auto-actionable **only when an existing oracle is currently RED**; the router becomes a
  pure nominator. **F1/F16 STOP by construction** (no AC asserts their concern → no RED oracle).
- Apply iff the oracle goes RED→GREEN, the full suite stays GREEN, paths ⊆ `allowed_paths`, and the
  patch edits **no** test/spec/oracle. **Never synthesize an AC-anchored test after seeing the finding**
  (reward-hacking) — oracles are authored at sign-off, frozen, author/fixer-separated.
- Anti-overfit second gate (residual is now *oracle adequacy* — SWE-bench Verified still shows ~8–30%
  test-passing-but-wrong): mutation score, property/fuzz, **behavioral-delta containment** (STOP if any
  behavioral change vs. pre-fix isn't authorized by an AC).

`oracle_gate.py` PASSES *and* surfaces the catch: against a real goal's happy-path acceptance commands
the oracle-covered subset is **~empty** (every review finding is about behavior no signed oracle
asserts), so auto-apply does real work only after you invest in stronger (property-based) oracles at
sign-off. Unlock an `--auto` mode only behind a frozen-oracle gate (false-auto=0 on the roadmap replay
+ adversarial wrong-but-green / test-editing patches). Until then: route + you-classify is correct.
