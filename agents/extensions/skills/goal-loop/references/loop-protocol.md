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
  "durability": "load_bearing",         // from the artifact frontmatter (default load_bearing); gates spec-review skip + the legibility guard
  "round": 2,
  "max_rounds": 2,
  "review_backend": "prism",            // prism|external|local|none
  "prism_config": "2",                  // forwarded verbatim (prism N [M]); "" => prism auto-sizes
  "spec_approved": true,                // true | "auto" (interactive sign-off | --auto freeze); frozen after
  "round_start_ref": "a1b2c3d",         // git rev captured on entering drive/fix this round (diff baseline)
  "rounds": [
    { "round": 1, "round_start_ref": "0f9e8d7", "drive_marker": "GOAL-DRIVE COMPLETE: <id> — …",
      "legibility_delta": "same",       // better|same|worse — from the review's legibility lens; two consecutive "worse" → legibility_regression HALT
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
| drive → review | `round_start_ref` FIRST (on entering drive, **before** goal-drive — the pre-patch diff baseline); then goal-drive patches + marker; then phase | marker present, phase `drive` → set `review` (goal-drive reconciles its units); `round_start_ref` absent → re-capture before driving |
| review → classify | `review-rN.md`; then `findings.json`; then phase | **findings file exists → skip to classify** (never re-dispatch review) |
| classify → fix | full `disposition` + `fix-rN.checklist.json`; then phase | partial/empty disposition → re-present the actionable batch; write nothing until `approve` |
| fix → review | `round_start_ref` FIRST (on entering fix, **before** goal-drive — the pre-patch baseline for the re-review); then goal-drive drives child checklist + marker; then phase + `round+1` | mid-fix crash → goal-drive's reconcile-from-artifact resumes |

**Write durability & concurrency.** Every ledger/JSON write is **atomic** — write a temp file in `.goals/`
and `rename` it over the target (atomic on one filesystem), so a crash mid-write never leaves a torn
`loop.json`/`findings.json`. A single `.goals/<id>.lock` (created `O_EXCL` on entry, removed on
STOP/COMPLETE) guards against a **second concurrent goal-loop on the same id** clobbering the ledger — if
the lock exists and its pid is live, stop and say so; if stale (dead pid), reclaim it. On resume, before
trusting `round_start_ref`, **detect a stale worktree**: if `git rev-parse HEAD` no longer matches the
ledger's recorded ref (history rewritten or branch switched), STOP and reconcile against the repo rather
than diffing a baseline that no longer exists. The working tree may hold a *concurrent session's*
uncommitted work — never revert it (inherit goal-drive's authority rail).

## Spec review (mod #1)

**On by default**, between `elicit` and `drive` (config `1`); **skipped by `--no-spec-review`, for a
Clear-domain one-shot artifact** (goal-elicit's triage = Clear), **or for a `mechanical`/`disposable`
artifact** (durability — a verifiable transform with a real oracle, or a short-shelf-life output, carries little spec-quality tax);
override depth with `--spec-review
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

**Author oracles here (optional, the `--auto` lever).** Sign-off is the one safe moment to write the
**frozen-oracle manifest** (`.goals/<id>.oracles.json`, schema in § The frozen-oracle manifest): executable
acceptance oracles for the mechanically-checkable criteria, frozen with the spec's `spec_sha256`. They do
nothing for interactive runs, but they are exactly what lets a later **`--auto`** run safely auto-fix
(a finding whose AC-oracle is RED → apply on RED→GREEN). Author them now, author/fixer-separated and before
any implementation review — never synthesize one after seeing a finding (reward-hacking). Validate with
`scripts/oracle_manifest.py validate <manifest> <artifact>`. Skipping them is fine — `--auto` then defers
everything instead of auto-fixing.

## Durability — tuning autonomy to shelf life

On entering the loop, read the artifact's `durability` frontmatter field (goal-elicit's Phase 0 axis:
`mechanical | disposable | load_bearing`; **default `load_bearing` if absent or unreadable** — the
conservative choice) and persist it on `loop.json`. It encodes *how trustworthy a hands-off loop is for
this output*, which the post's distinction (where-loops-work vs. lasting-code authorship) makes orthogonal
to scope and clarity: loops are reliable when
they transform existing code (`mechanical`) or make short-lived artifacts (`disposable`), and risky when
they author lasting code (`load_bearing`) unattended — that is where defensive sprawl accretes and
comprehension erodes. It tunes exactly two levers, nothing else (it never changes what is fixable or
relaxes the two non-negotiables):

| `durability` | Spec-review | Legibility lens + regression guard |
|---|---|---|
| `mechanical` | auto-skipped *when the transform is verifiable via a real oracle* — little spec-quality tax | lens reports advisory; `worse` does **not** halt |
| `disposable` | auto-skipped (short shelf life) | lens reports advisory; `worse` does **not** halt |
| `load_bearing` | runs by default | lens **mandatory**; two consecutive `worse` → `legibility_regression` HALT |

A `mechanical`/`disposable` classification is a claim the operator made at elicit time; if the diff is in
fact authoring lasting load-bearing code, that is a spec error to surface, not a reason to silently widen
autonomy. Under `--auto`, `load_bearing` additionally means an `AUTO-COMPLETE` is **blocked** while the
latest `legibility_delta` is `worse` (it becomes `AUTO-HANDOFF` with the legibility findings queued) — the
loop never reports a lasting-code goal "done" on a round that made it less comprehensible. A `load_bearing`
legibility finding whose fix exceeds the unit's `allow_paths` or trips a one-way-door keyword routes to
`needs_user` (see The router); under `--auto` that biases toward **AUTO-HALT**, never the default
defer-and-continue — otherwise a structural "remove the machinery" fix would queue in the morning report
while the loop keeps amplifying.

This bounds the **per-round** legibility of one goal's diff; it does **not** address the codebase-level
*cognitive dependency* the post calls its "scariest part" — a system becoming loop-built, loop-reviewed,
loop-maintained, and no longer humanly explicable. No single goal artifact can own that portfolio-level
trajectory; treat it as out of scope here, not solved.

## The router — nominator, not apply-authority

After review, the router **mechanically** disposes the bulk so you don't read it, and surfaces only the
actionable batch. It is a deterministic procedure (model self-classification was ~17% reliable):

```
for each finding (claim/proposed_fix), set scope mechanically:
   distinctive-term overlap of (claim + proposed_fix) vs each acceptance/done_when/constraint — a term
   counts only if it is identifier-shaped (snake_case, dotted, `method-…`, or a known code symbol),
   appears in ≤2 ACs, and is neither a stopword nor a generic domain word. The frozen STOP / GEN / KNOWN
   term sets and the exact procedure are canonical in `scripts/empirical_gate.py::route` — keep this doc
   and that script in sync rather than re-specifying a bare threshold here that can drift:
     shares a distinctive term with exactly one AC → in_scope-mapped, maps_to = that AC id
     zero                                          → in_scope-unmapped
     two+ ACs, no common distinctive term (ambiguous) → needs_user    # fail closed — never guess
   severity == could                                → out_of_scope
   recurrence (same maps_to OR ≥50% claim-overlap with an accepted+fixed prior finding) → needs_user
   proposed_fix ∉ authority.allow_paths             → needs_user
   one-way-door keywords (delete|drop|migrate|deploy|publish) → needs_user

auto-dispose (kept off your decision path, but summarized — not invisible):
   out_of_scope → DEFER (ledger; print a suggested `## Emergent` line; source untouched)
   needs_user   → STOP (surface the reason; the loop halts for you)
print a one-line DEFERRED/STOP audit before the batch: counts by scope+severity, the titles of any
   DEFERRed `blocker`/`should` (a deferred high-severity finding is the case most worth a glance), and
   `expand <id>` to read any deferred item in full — the bulk stays off the decision path, not hidden.
surface the ACTIONABLE batch (in_scope-mapped + in_scope-unmapped) for your decision:
   you bucket each → accepted (a fix item) | deferred | rejected;
   in_scope-unmapped accepted ⇒ you author the new acceptance line first.
nothing is written to fix-rN.checklist.json until you `approve` the batch.
```

Severity does **not** decide actionability: the roadmap's loud NO-SHIP finding had no AC → surfaced as
`in_scope-unmapped` (you out-scope it), not auto-fixed; the consensus refactor of correct code →
out-of-scope → DEFER. **The router is a fail-closed triage, not a replica of human judgment** — it
reaches the same *action* (don't auto-fix) by a different *mechanism* (no covering AC), and its lexical
mapping is unreliable in **both** directions: it false-maps on a shared identifier that names a
*different* concern (F1/F16) and false-STOPs genuinely-mapped findings (F2/F3) — both reproduced by
`scripts/empirical_gate.py`. So its load-bearing, trustworthy work is the cheap bulk **DEFER** of
`could`/refactor/one-way-door findings plus **fail-closed surfacing** of everything else; treat its
`maps_to` as a *nominee* you confirm or `reassign`, never the apply authority (see *The path beyond
report-only*).

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
router and classify gate are mechanical only *afterward*) — and the one place a model error silently
reshapes the batch, so it **fails closed**: read `review-rN.md`; extract distinct actionable findings,
**dedupe by claim**; assign ids `R{N}-F{nn}`; fill severity / claim / proposed_fix / proposed_acceptance
/ proposed_verification, and a `source_review` anchor (`review-rN.md#finding-k`) for each; leave
scope/maps_to/status for the router + you. **Validate every record against the finding schema before
writing** — a record missing a required field, carrying an unknown severity, or lacking a `source_review`
anchor is a failed extraction → do **not** write a partial `findings.json`; STOP
(`stop_reason: normalization_failed`) and re-extract. Then write `findings.json`, print one reconciliation
line — `prism raised <N> distinct points → extracted <M> findings` (spot-check when N≫M: a dropped
finding is the silent failure here) — and advance `current_phase=classify`.

### Oscillation rule

A round-N finding **recurs** if its `maps_to` equals that of an accepted+fixed finding from **any prior
round**, or its `claim` shares ≥50% key terms with one. Compute at classify time by scanning all prior
`findings.json`. On recurrence → `stop_reason: oscillation`, do not write the fix, emit `GOAL-LOOP STOPPED`.

### Legibility regression rule

The legibility lens ends each review with `legibility_delta: better|same|worse`; record it on the round
ledger entry. If **two consecutive rounds report `worse`** — the fix loop is ratcheting up defensive
machinery faster than it removes error classes, i.e. the code "appears more robust while becoming less
understandable" — HALT: `stop_reason: legibility_regression`, emit `GOAL-LOOP STOPPED`, and hand back so a
human re-reads the cumulative diff before more rounds compound it. A **single** `worse` round does **not**
halt — its legibility findings just surface in the normal actionable batch (that's the per-round jolt).

`legibility_delta` is a **subjective, reviewer-judged signal — not an objective measurement.** In the
post's own terms it is a signal "useful enough to drive another iteration" (here, a human re-read), never a
quantitative bound; it is a **liveness** guard alongside oscillation and `findings_escalating`, not proof
the ratchet was prevented. It is not game-proof — a non-monotone `worse/same/worse` pattern slips the
two-consecutive gate — so the **real defense is the per-round lens findings** (`should`+, surfaced); this
HALT only bounds *continued compounding*. For a `load_bearing` review the lens **MUST emit exactly one
parseable `legibility_delta`**; a missing or unparseable value **fails closed** — `normalization_failed`
interactively, `AUTO-HALTED legibility_regression` under `--auto` — never a silent `same`. Prior rounds with
no recorded delta (e.g. an artifact upgraded mid-loop) count as **neutral** — a missing value never forms a
`worse` pair.

**Relaxed for a `mechanical`/`disposable` artifact** (durability): the lens still reports, but `worse` does
not halt — those outputs are short-shelf-life by design, so comprehensibility of the code is not load-bearing.

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
### Legibility lens (the loop's second failure mode)
Also judge whether this round made the code LESS COMPREHENSIBLE WHILE APPEARING MORE ROBUST — the
characteristic damage a fix loop does. Flag as distinct findings: fallbacks/guards added for states the
design could make unrepresentable; handling of states that cannot occur; defensive duplication; new
abstraction or machinery that papers over unclear design; net complexity growth with no error class
removed. Rate these `should` MINIMUM (`blocker` when an invariant is actually violated) — NEVER `could`,
so the router cannot silently defer them — and let each proposed fix REMOVE machinery or make the bad
state unrepresentable, not add more. End the review with one line —
`legibility_delta: better|same|worse — <one clause>` — where **`worse`** = this round added defensive
machinery/complexity with no error class removed; **`same`** = net neutral (some added and some removed, or
none found); **`better`** = a net reduction in machinery or complexity. (The per-round signal the
legibility_regression guard reads; it is a subjective judgement, not a measurement — see the rule.)
### Source artifact
<path + the acceptance_criteria / done_when / constraints block, verbatim>
### What changed
<git diff --stat since round_start_ref, + changed file list>
### Verification evidence
<the GOAL-DRIVE COMPLETE marker line + the real verification output it printed>
```

For `--review prism`, forward `prism_config` verbatim ahead of the packet (`Skill(prism, "2 <packet>")`).
Rating legibility findings `should`+ keeps them off the `could → out_of_scope → DEFER` auto-path; the
guarantee is **surfaced or fail-closed**, not specifically `in_scope-unmapped`. Most carry no acceptance line
and route to `in_scope-unmapped` (**surfaced**; accept ⇒ author the acceptance line first). But a structural
fix that *removes machinery* often exceeds the unit's `allow_paths` or trips a one-way-door keyword → the
router routes it to `needs_user` instead: interactively a **surfaced scope call** (a STOP, not silently
lost); under `--auto` it biases toward **AUTO-HALT** (§ Durability), not the default defer-and-continue.
**The in-loop "jolt" is interactive only** — under `--auto`, legibility findings land in the morning report /
`AUTO-HANDOFF` queue (a deferred review), not an in-loop comprehension prompt. The `legibility_delta` is
recorded in the round ledger and drives the **Legibility regression rule** above. For a `mechanical`/`disposable`
artifact (durability), the lens still reports but is advisory — see § Durability.

## The path beyond report-only — oracle-gating (realized by `--auto`)

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
sign-off. The `--auto` mode below unlocks exactly this frozen-oracle gate (false-auto=0 on the roadmap
replay + adversarial wrong-but-green / test-editing patches) and **nothing more** — with no oracles it
auto-fixes nothing and defers, which is "route + you-classify" with the classify *deferred to a morning
queue* instead of blocking on you live.

## Autonomous mode — `--auto` (unattended, under native `/goal`)

`--auto` lets goal-loop run **unattended** (operator asleep) under Claude Code's native `/goal` command.
`/goal`'s evaluator fires only **after a turn finishes** and is **tool-less** (judges only the transcript),
so the interactive gates' `AskUserQuestion` calls would **deadlock the turn forever**. `--auto` therefore
replaces **both** human gates with **fail-closed autonomous policies** and terminates on **printed markers**
the evaluator can see. It changes only goal-loop's *gate behavior, termination, and handoff* — goal-drive,
prism, goal-elicit, the router, the ledger, and crash-safety are unchanged. Design synthesis (prism `2 2`,
15 perspectives, no cross-model dissent): `~/.ai/reports/20260616-2243-goalloop-auto-design.md`.

**Precondition — `--auto` requires a ready artifact; it never interviews.** The deadlock is not limited to
the two gates: the **elicit** phase interviews via `AskUserQuestion` too, so `--auto -- "<vague request>"`
with no spec would deadlock the `/goal` turn. Therefore `--auto` requires a `status: ready` artifact —
`--artifact <path>`, or a pre-existing `.goals/<id>.goal.md` (resolved by `continue`). If none exists, or
elicit would need to interview to reach `ready`, `--auto` emits **`GOAL-LOOP AUTO-HALTED: <id> —
needs_artifact`** *before* any `AskUserQuestion` — run `goal-elicit` interactively first, then launch
`--auto` on the resulting artifact. (The README's overnight recipe pastes `/goal` at an existing
`.goals/<id>.goal.md` for exactly this reason.)

**The honest value, stated up front.** `--auto` delivers *drive → multi-model review → auto-fix only the
frozen-oracle-RED subset → a tight pre-classified morning decision queue.* It does **not** make the
operator's scope judgment. Because oracle coverage is ~empty by default (above), a first run typically
**auto-fixes nothing** and produces a full decision queue — that is correct behavior, **not** a failure;
the morning report and docs must say so plainly so the operator is not surprised. The only lever that grows
the auto-fix set is the operator authoring stronger (property/fuzz) oracles **at sign-off** — unavailable
unattended that night.

### Gate A under `--auto` — spec-review never auto-edits the spec

`--auto` **freezes the elicited spec as-is** as binding authority and runs spec-review **report-only**: the
strengthened-spec findings (proposed new ACs, gaps, contradictions) are written to the **morning report**,
and **nothing is applied** to the artifact. This captures the spec lever's *information* for the morning
(the operator gets the exact new-AC candidates to author and re-run) with **zero unattended
scope-mutation surface**. `--no-spec-review` skips even the report-only pass. On a contradiction that blocks
driving → STOP-HALT (`spec_contradiction`). Set `spec_approved: auto` + a content hash at freeze.

> **Ideal upgrade (not shipped).** A bounded, *semantics-preserving* auto-strengthen via an `auto_contract`
> overlay — apply only monotone metadata/binding ops (add stable `ac_id`s; attach a verification command
> **already in `allow_commands`** to an existing `done_when`; narrow `allow_paths`; mark a non-mechanical AC
> `oracle: manual`; add a preservation constraint derived from existing `scope_out`). It must **never**
> reword an acceptance predicate, add a new AC, expand `scope_in`, or relax `scope_out`. Deferred because the
> "is-this-monotone?" check leans on the same lexical mechanism that is unreliable in both directions, and
> goal-elicit's Phase-5 hard gate already forces `done_when` to be testable — so the marginal gain doesn't
> justify the added scope-mutation surface in the minimum-viable mode.

### Gate B under `--auto` — the auto-disposition policy

The router runs unchanged (it fills `scope`/`maps_to` mechanically). The **classify gate becomes
deterministic** — no `AskUserQuestion`. **Oracle-gating is REQUIRED for every auto-accept; cross-model
consensus/confidence may only raise a finding's queue *priority*, never authorize a patch** (LLM judges
share self-preference bias and can confidently agree on plausible-but-out-of-scope work — METR
reward-hacking, the F8 loud-NO-SHIP scope-vs-truth case). The auto-action per finding class:

| Finding class | `--auto` action |
|---|---|
| `in_scope-mapped` blocker/should, exactly one `maps_to`, **existing frozen oracle currently RED** | **AUTO-FIX** — build a `fix-rN` item bound to `{finding, ac_id, oracle_id}`; apply **iff** the oracle flips RED→GREEN **and** the full suite stays GREEN **and** patch paths ⊆ `allow_paths` **and** the patch edits **no** test/spec/oracle **and** the behavioral delta is authorized by the flipped oracle **and** anti-overfit passes (the exact `oracle_gate.py` gate) |
| `in_scope-mapped`, oracle **GREEN** | **DEFER** to the morning queue (plausible, but no failing contract proves it) |
| `in_scope-mapped`, **no oracle / `oracle: manual`** | **DEFER** to the morning queue (carry the proposed AC/verification as a *suggestion*) |
| `in_scope-mapped`, ambiguous `maps_to` or path ∉ authority | **DEFER** (or STOP-HALT if `blocker`) — the nominee is unreliable; fail closed |
| `in_scope-unmapped` (real defect, no AC) | **DEFER** to the morning queue, top of stack — accepting requires authoring a new acceptance line = **scope authorship**, forbidden to an unattended reviewer (invariant #2) |
| `could` / `out_of_scope` | **DEFER** to the ledger (counted + titled in the audit; never patches the source) |
| `needs_user` (scope call) | **DEFER** to the queue and **continue** the loop (deferring a scope call ≠ making it) — *unless* it blocks the drive from making progress, then **STOP-HALT** (`needs_user`) |
| one-way-door (`delete\|drop\|migrate\|deploy\|publish`) | **STOP-HALT** (`one_way_door`) |
| recurrence / oscillation | **STOP-HALT** (`oscillation`) |
| normalization failure (missing anchor / unknown severity / `N ≫ M`) | **STOP-HALT** (`normalization_failed`); never write a partial `findings.json` |

**Nothing is written to a `fix-rN` checklist except AUTO-FIX items.** During a fix round, the child fix
artifact's `authority.allow_paths` **excludes** all test/spec/oracle paths, so the fixer *cannot* edit an
oracle (reward-hacking guard, enforced not requested).

### The frozen-oracle manifest — `.goals/<id>.oracles.json` (what makes AUTO-FIX possible)

AUTO-FIX consults a **frozen-oracle manifest**: the operator's executable acceptance oracles, authored **at
sign-off** (interactive spec-review, or alongside goal-elicit) and frozen with the spec. It is the concrete
form of the oracle-gating upgrade path (§ The path beyond report-only); `scripts/oracle_manifest.py`
validates it and computes each oracle's live RED/GREEN, and `scripts/oracle_gate.py` is the offline proof
that gating on it is safe (false-auto=0). **Author/fixer separation is structural: the manifest is written
before any implementation review, frozen with a `spec_sha256`, and a fix round can never edit it (its paths
are excluded from the fix `allow_paths`).**

```json
{ "schema_version": "goal-oracles/v1", "id": "<goal id>",
  "source_artifact": ".goals/<id>.goal.md", "spec_sha256": "<hash of the frozen spec at sign-off>",
  "oracles": [
    { "ac_id": "AC-3", "oracle_id": "O1", "kind": "mechanical",
      "command": "pytest tests/test_set_same.py -q",   // exit 0 = GREEN (satisfied); non-zero = RED (failing)
      "allowed_paths": ["src/method.py"],               // a fix for this AC may touch only these
      "preservation": ["pytest -q"] },                  // command(s) that must STAY green (regression guard)
    { "ac_id": "AC-5", "oracle_id": "O2", "kind": "manual", "command": null } ] }
```

- Every `ac_id` must exist in the frozen artifact; `oracle_id`s are unique; `mechanical` oracles carry a
  `command` (+ `allowed_paths`/`preservation` as non-empty-string lists), `manual` ones carry `command: null`
  and are **never** auto-fixable. The manifest also carries `spec_sha256` — the hash of the frozen spec block
  (objective + acceptance/done_when + scope + constraints + authority) at sign-off.
- **`--auto` validates the manifest strictly before trusting it (fail-closed against a stale registry):**
  `oracle_manifest.py validate <manifest> <artifact> --strict` — a missing/malformed `spec_sha256`, or any
  `ac_id` not present in the artifact, is a **hard error → STOP-HALT `stale_oracle_manifest`** (not a
  warning). At entry `--auto` also re-derives the frozen spec block's hash and compares it to
  `spec_sha256`; a mismatch means the spec changed since sign-off → **STOP-HALT `stale_oracle_manifest`**
  rather than gate an auto-fix against a stale oracle. (This precondition runs once, before any drive
  mutates state.)
- **Consumption by AUTO-FIX:** a finding is AUTO-FIX-eligible iff it is `in_scope-mapped` to `AC-k` **and**
  the manifest has a `mechanical` oracle for `AC-k` that `oracle_manifest.py evaluate` reports **RED** (a
  TIMEOUT/unknown oracle is **not** RED and is **not** GREEN — see Termination). The fix is then applied
  **iff** that oracle flips RED→GREEN, every `preservation` command stays GREEN, the patch paths ⊆ the
  oracle's `allowed_paths`, the patch edits no test/spec/oracle, and the behavioral delta is authorized by
  the flipped oracle. **`oracle_manifest.py` supplies only the RED/GREEN state; the rest of this gate
  (preservation, path-containment, no-test/spec/oracle-edit, behavioral-delta, anti-overfit) is enforced by
  this `--auto` protocol, not by any script** — `oracle_gate.py` is the offline *proof* the gate is safe
  (false-auto=0), never a live enforcer. (The oracle's per-oracle `allowed_paths` and the fix round's
  `allow_paths` are **distinct path-sets, both enforced** — a patch must fall within the oracle's allowed
  paths *and* the fix authority, which additionally excludes every test/spec/oracle path.)
- **No manifest, or no RED oracle ⇒ AUTO-FIX is empty** — `--auto` auto-fixes nothing and defers the whole
  batch. This is the expected default until the operator invests in oracles at sign-off (the honest caveat
  above). Coverage accrues run-over-run as the operator authors more oracles.

### The `--auto` loop dynamic

Rounds are driven **only** by the oracle-RED auto-fix subset:

```
record round_start_ref FIRST → goal-drive (Skill, inline) → review (backend) → normalize (fail-closed)
→ router → AUTO-FIX = the oracle-RED subset; everything else DEFERs/HALTs (table above)
if AUTO-FIX is non-empty: write fix-rN (AUTO-FIX items only) → record round_start_ref → goal-drive the
   fixes → re-review (round+1)
else (no oracle-RED auto-fixable finding this round): CONVERGE
repeat until CONVERGE (→ AUTO-COMPLETE if the decision queue is empty, else AUTO-HANDOFF)
   OR round > max_rounds (→ AUTO-HALTED: max_rounds) OR a STOP-HALT condition (→ AUTO-HALTED: <reason>)
```

needs_user/deferred findings **never** trigger another round by themselves — only oracle-RED work does — so
the loop is naturally bounded and most runs (empty oracle coverage) converge after round 1's review with a
full deferred queue.

### Termination — three printed markers + an evidence block

`--auto` ends in exactly one terminal state, each a **literal marker line** (not prose) the tool-less
`/goal` evaluator keys on, **preceded** by an evidence block in the transcript:

- `GOAL-LOOP AUTO-COMPLETE: <id>` — drive verified-done; **every frozen mechanical oracle GREEN** (a
  TIMEOUT/unknown oracle is NOT GREEN and **blocks** COMPLETE → AUTO-HANDOFF or, if it can't be resolved,
  AUTO-HALTED `oracle_timeout`); every auto-accepted RED-oracle finding fixed + re-reviewed; **and the human
  decision queue is empty.** The *decision queue* = `in_scope-unmapped` + `in_scope-mapped`-no-oracle +
  `needs_user` (the items only a human can dispose); `could`/`out_of_scope` are **audit-only** deferrals that
  do NOT block COMPLETE. Ledger: `current_phase=done`, `stop_reason=null`, `auto_terminal=complete`.
- `GOAL-LOOP AUTO-HANDOFF: <id>` — all authorized automated work converged, but a **non-empty decision
  queue** remains for human classification. **The common case.** A clean `done` (not a halt), distinguished
  from COMPLETE only by the non-empty queue, so it carries **no** `stop_reason`. Ledger: `current_phase=done`,
  `stop_reason=null`, `auto_terminal=handoff`.
- `GOAL-LOOP AUTO-HALTED: <id> — <reason>` — a safety/liveness fault; `reason` ∈ {`needs_artifact` (no
  ready spec to drive — see Precondition), `needs_user` (blocker), `one_way_door`, `oscillation`,
  `normalization_failed`, `stale_baseline`, `lock_conflict`, `unauthorized_path`, `stale_oracle_manifest`,
  `oracle_timeout` (a mechanical oracle never resolves GREEN/RED), `review_backend_unavailable` (when review
  was required), `max_rounds`, `spec_contradiction`, `legibility_regression` (two consecutive `worse`
  legibility deltas on a `load_bearing` goal, or a missing/unparseable delta)} — each produced by a rule in the policy table,
  Precondition, or hardening section. Ledger: `current_phase=stopped`, `stop_reason=<reason>`,
  `auto_terminal=halted`.

Print the evidence block *before* the marker, into both the transcript and the report:

```
GOAL-LOOP AUTO EVIDENCE-BEGIN
drive_marker=GOAL-DRIVE COMPLETE: <id> — …
review_backend=<prism|local|none>  review_points=N  findings=M  normalization=ok
oracles: total=T red_before=R red_after=Ra green=G timeout=Ti manual=Mo   # AUTO-COMPLETE requires red_after=0 AND timeout=0 (every mechanical oracle GREEN)
verification: <command> exit=0
full_suite: <command> exit=0
protected_files_edited=false  allowed_paths_only=true
deferred_counts: mapped_no_oracle=A unmapped=B could=C out_of_scope=D needs_user=E recurrence=F
GOAL-LOOP AUTO EVIDENCE-END
```

The marker is a **liveness** mitigation, **not a security boundary** — a tool-less evaluator can be fooled by
fabricated text; the real safety is the deterministic gate above + goal-drive's no-verification-theater rule
(`/goal` is the seatbelt, the gate is the brakes). **AUTO-COMPLETE requires an empty human *decision queue*
(`in_scope-unmapped` + `in_scope-mapped`-no-oracle + `needs_user`); `could`/`out_of_scope` are audit-only
deferrals that don't block it. A round that only deferred decision-queue items is an AUTO-HANDOFF, never
AUTO-COMPLETE.**

**Ready-to-paste `/goal` condition** (≤4000 chars; all three markers are SATISFIED states, so the hook never
fights a legitimate halt):

```
/goal "Drive <ARTIFACT> id <ID> through goal-loop --auto; resume each turn with `goal-loop continue <ID>`. SATISFIED when the transcript contains a line beginning 'GOAL-LOOP AUTO-COMPLETE: <ID>', 'GOAL-LOOP AUTO-HANDOFF: <ID>', or 'GOAL-LOOP AUTO-HALTED: <ID> —', with a 'GOAL-LOOP AUTO EVIDENCE-END' line and the real verification output (commands + exit codes, any RED→GREEN oracle ids) appearing earlier in the transcript — not a bare 'done' claim. Do not accept a narrated summary without that evidence block. TIMEOUT: if no such marker appears after <N> turns, stop and report the guardrail expired without a terminal marker — do not claim done."
```

`<N>` = a generous turn cap (see goal-elicit `references/goal-guardrail.md` § Turn-bound heuristic). The first
`/goal` paste *launches* `goal-loop --auto`; each subsequent turn resumes via `continue` until a marker clears it.

### The morning report — `.goals/<id>.auto-report.md`

Written **before** the terminal marker (so it survives a crash), built for minutes-long disposition:

1. **Outcome** — status (COMPLETE/HANDOFF/HALTED) + reason + round.
2. **What changed** — files, diff summary, allowed-path proof.
3. **Auto-applied fixes** — each `{finding, source anchor, ac_id, oracle_id, RED→GREEN proof, commit sha}`
   (independently revertible).
4. **Decision queue** (the only thing needing the operator) — the `in_scope-unmapped` + `mapped-no-oracle` +
   `needs_user` batch, grouped + severity-ordered, each as the *exact* interactive classify choice
   `{severity, claim, proposed_fix, proposed_acceptance, maps_to nominee, why-not-auto-accepted, suggested action}`.
5. **Deferred-bulk audit** — counts by scope+severity + titles of any deferred `blocker`/`should`.
6. **Resume** — the exact `goal-loop continue <id>` classify command to disposition the queue interactively.

### Unattended hardening (failure modes, biased toward HALT)

Same defenses as interactive mode, but with no human to catch a slip, `--auto` **fails toward HALT**:

- **Scope mutation** — spec frozen (no auto-edit); `in_scope-unmapped` always DEFERs; out-of-scope never
  patches the source. Every unattended write-path into scope is removed.
- **Reward-hacking / oracle-gaming** — oracles frozen at sign-off, author/fixer separated; the fix round's
  `allow_paths` excludes test/spec/oracle paths; AUTO-FIX requires RED→GREEN **and** full-suite GREEN **and**
  behavioral-delta containment; **never** synthesize an AC-anchored test after seeing a finding.
- **Oscillation / regression** — the recurrence rule (above) → STOP-HALT; additionally STOP if the *same
  oracle* goes RED again after a prior GREEN (a regressing fix would loop forever). The interactive
  `findings_escalating` stop_reason is **folded into these guards under `--auto`** (a round whose oracle-RED
  set grew after a fix is the regression signal) — it is not a separate `--auto` AUTO-HALTED reason;
  non-oracle escalating findings simply accrue in the morning queue. **Legibility regression** (two consecutive
  `worse` legibility deltas, `load_bearing` only — or a missing/unparseable delta) is handled here too, but
  because the delta has no oracle to fold into it is a **named AUTO-HALTED reason** (`legibility_regression`),
  not a fold: a single `worse` round blocks AUTO-COMPLETE (→ AUTO-HANDOFF with legibility findings queued); a
  second consecutive `worse`, or an unparseable delta, emits `GOAL-LOOP AUTO-HALTED: <id> — legibility_regression`;
  and a `load_bearing` legibility finding routed to `needs_user` biases toward AUTO-HALT rather than
  defer-and-continue. For `mechanical`/`disposable` the whole guard is inert (§ Durability).
- **False-positive `/goal` completion** — evidence block must precede the marker; AUTO-COMPLETE forbidden on a
  DEFER-only round; TIMEOUT bounds a stuck run with a TIMEOUT *report*, not "done".
- **Normalization loss** — schema-validate every record, **fail closed**; mandatory `source_review` anchor;
  print `review points N → findings M`; **escalate to STOP-HALT when `N ≫ M`** (drop > ~20%) rather than the
  interactive print-and-continue — no one is watching the print.
- **Concurrent worktree / stale baseline** — `.goals/<id>.lock` (O_EXCL, live-pid check → STOP-HALT
  `lock_conflict`); atomic temp+rename writes; STOP-HALT `stale_baseline` on `git rev-parse HEAD` ≠ recorded
  ref or dirty unowned paths; a fix whose paths ⊄ authority → STOP-HALT `unauthorized_path`; **never revert
  unknown/concurrent uncommitted work**. Commit per auto-fix (`commit_policy: per_unit`) for independent
  revert.

### Optional hardening (operator opt-in)

Two stronger guarantees the operator can opt into for a high-stakes overnight run — neither is required
(the defaults above are already safe), so they are options, not part of the minimum mode:

- **Worktree isolation (`--worktree`).** Run the `--auto` loop in a fresh `git worktree` dedicated to this
  run, so a concurrent session sharing the main checkout can neither be clobbered by nor clobber the run.
  goal-drive/goal-loop operate inside the isolated worktree; on COMPLETE/HANDOFF the operator merges it back.
  This upgrades the concurrent-worktree defense from *detect-and-HALT* (the default) to *cannot-collide*.
  Cost: a worktree per run (disk + setup), so it is opt-in, not default.
- **Deterministic completion Stop-hook.** The `/goal` marker is a *liveness* signal a tool-less evaluator
  reads from the transcript — fakeable in principle. For a stronger stop surface, the operator can register a
  **command** Stop-hook that greps the transcript/ledger for a real `auto_terminal` + verifies the evidence
  deterministically (e.g. re-runs the top-level verification command), instead of relying on the Haiku
  evaluator. This makes completion a *checked* fact, not a *judged* one. It lives in the operator's
  `settings.json` (a harness config, outside this skill); goal-loop just emits the marker + evidence the hook
  consumes. Recommended for unattended runs that apply fixes; unnecessary for review-and-defer-only runs.

### Portability under `--auto`

`--auto` is resolved by **capability, not runtime**. If the review backend is unavailable (off-Claude prism
refuses, or `--review local` single-model with no cross-model independence): **no auto-fix at all** — drive +
verification only, note `review_unavailable` in the round status, write the report, and STOP-HALT with
`stop_reason: review_backend_unavailable` (the round-status note and the stop_reason are two fields for the
one condition) — or, with `--review none`, emit **`GOAL-LOOP AUTO-COMPLETE: <id>`** after the drive marker
(a deliberate drive-only run; no review ⇒ the decision queue is empty by construction; `auto_terminal=complete`).
**Under `--auto` every terminal is one of the three `AUTO-*` markers — never the interactive
`GOAL-LOOP COMPLETE (no-review)`, which the `/goal` condition does not match (it would hang until TIMEOUT).**
`--auto` never fakes cross-model review and never auto-accepts on single-model output.

### Ledger additions for `--auto`

The `.loop.json` ledger gains `"auto": true`, an `"auto_report": ".goals/<id>.auto-report.md"` pointer, and
an `"auto_terminal"` field ∈ {`complete`, `handoff`, `halted`} set at termination. **COMPLETE and HANDOFF
are both clean `current_phase=done` with `stop_reason=null`** (distinguished by `auto_terminal` + the
decision-queue count), preserving the schema invariant that `stop_reason` is set **only** on
`current_phase=stopped` — which is AUTO-HALTED, carrying the `--auto` `stop_reason` values above. Everything
else (index-only, files-win, atomic writes) is unchanged.
