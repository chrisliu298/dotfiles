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
prism, goal-elicit, the router, the ledger, and crash-safety are unchanged. Design synthesis (prism `2 h 2gp`,
15 perspectives, no cross-model dissent): `~/.ai/reports/20260616-2243-goalloop-auto-design.md`.

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

- `GOAL-LOOP AUTO-COMPLETE: <id>` — drive verified-done, all frozen mechanical oracles GREEN, every
  auto-accepted RED-oracle finding fixed + re-reviewed, **and the decision queue is empty** (only
  `could`/`out_of_scope` deferred). Ledger: `current_phase=done`, `stop_reason=null`, `auto_terminal=complete`.
- `GOAL-LOOP AUTO-HANDOFF: <id>` — all authorized automated work converged, but a **non-empty decision
  queue** remains for human classification. **The common case.** A clean `done` (not a halt), distinguished
  from COMPLETE only by the non-empty queue, so it carries **no** `stop_reason`. Ledger: `current_phase=done`,
  `stop_reason=null`, `auto_terminal=handoff`.
- `GOAL-LOOP AUTO-HALTED: <id> — <reason>` — a safety/liveness fault; `reason` ∈ {`needs_user` (blocker),
  `one_way_door`, `oscillation`, `normalization_failed`, `stale_baseline`, `lock_conflict`,
  `unauthorized_path`, `review_backend_unavailable` (when review was required), `max_rounds`,
  `spec_contradiction`} — each produced by a rule in the policy table or hardening section below. Ledger:
  `current_phase=stopped`, `stop_reason=<reason>`, `auto_terminal=halted`.

Print the evidence block *before* the marker, into both the transcript and the report:

```
GOAL-LOOP AUTO EVIDENCE-BEGIN
drive_marker=GOAL-DRIVE COMPLETE: <id> — …
review_backend=<prism|local|none>  review_points=N  findings=M  normalization=ok
oracles: total=T red_before=R red_after=0 green=G manual=Mo
verification: <command> exit=0
full_suite: <command> exit=0
protected_files_edited=false  allowed_paths_only=true
deferred_counts: mapped_no_oracle=A unmapped=B could=C out_of_scope=D needs_user=E recurrence=F
GOAL-LOOP AUTO EVIDENCE-END
```

The marker is a **liveness** mitigation, **not a security boundary** — a tool-less evaluator can be fooled by
fabricated text; the real safety is the deterministic gate above + goal-drive's no-verification-theater rule
(`/goal` is the seatbelt, the gate is the brakes). **Never emit AUTO-COMPLETE on a round whose only action was
DEFER.**

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
- **Oscillation** — the recurrence rule (above) → STOP-HALT; additionally STOP if the *same oracle* goes RED
  again after a prior GREEN (a regressing fix would loop forever).
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

### Portability under `--auto`

`--auto` is resolved by **capability, not runtime**. If the review backend is unavailable (off-Claude prism
refuses, or `--review local` single-model with no cross-model independence): **no auto-fix at all** — drive +
verification only, note `review_unavailable` in the round status, write the report, and STOP-HALT with
`stop_reason: review_backend_unavailable` (the round-status note and the stop_reason are two fields for the
one condition) — or, with `--review none`, emit `GOAL-LOOP COMPLETE (no-review)` after the drive marker.
`--auto` never fakes cross-model review and never auto-accepts on single-model output.

### Ledger additions for `--auto`

The `.loop.json` ledger gains `"auto": true`, an `"auto_report": ".goals/<id>.auto-report.md"` pointer, and
an `"auto_terminal"` field ∈ {`complete`, `handoff`, `halted`} set at termination. **COMPLETE and HANDOFF
are both clean `current_phase=done` with `stop_reason=null`** (distinguished by `auto_terminal` + the
decision-queue count), preserving the schema invariant that `stop_reason` is set **only** on
`current_phase=stopped` — which is AUTO-HALTED, carrying the `--auto` `stop_reason` values above. Everything
else (index-only, files-win, atomic writes) is unchanged.
