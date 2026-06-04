# The execution loop — in full

The operational core of goal-drive: the loop, what stops it, how it writes state so it
survives interruption, and how it commits. It is a closed control loop (observe → orient
against the contract → act → **verify** → checkpoint), supervised by **objective and
exception**, not by per-step approval. Read this before driving the first unit; read
`artifact-formats.md` before interpreting a bring-your-own artifact.

## The loop

```
1. LOAD      read the artifact. Determine work_shape, commit_policy, repair_budget (default 3),
             authority (fall back to Default authority in artifact-formats.md, and announce it).
             For a markdown artifact, set frontmatter status: running.
2. RECONCILE compare claimed state against repo reality (see "Resumption"). Surface drift; never
             trust a stale `done`.
3. SELECT    pick the next unit:
               checklist → the next `batch_size` items with state=pending
               phased    → the first phase whose `[state:]` marker is not `done`
               contract  → the whole goal (one unit); its `done_when` items are sub-units
             If none remain → go to 8.
4. ANNOUNCE  say what you are about to do in 1–3 lines: the unit + its acceptance check.
             Declarative, NOT a permission request — the contract already authorized this.
5. ACT       do the work, strictly inside `authority` (allow_paths / allow_commands) and scope
             (scope_out / anti-goals). Reversible, in-scope actions only without asking.
6. VERIFY    run the unit's acceptance (acceptance_per_item / phase Acceptance / each done_when item).
             Surface the verifier's REAL output into the transcript — the command + a bounded
             excerpt of its result / exit code (≤~20 lines), not just a pass/fail claim. The
             status-line summary is a claim; the raw output is the evidence (see Terminal markers).
               pass → LEDGER it (step 7)
               fail → repair, up to `repair_budget` attempts (default 3), recording each failed
                      attempt in the unit's evidence/note. Still failing → mark the unit
                      `blocked` with the reason, write it to the artifact, and STOP. Do not advance.
7. LEDGER    flip the unit to `done` and record evidence (command + result summary, file path,
             metric, or observed behavior). PATCH the artifact in place. THEN, iff
             commit_policy == per_unit, make one local commit for this verified unit. Emit the
             status line. Loop to 3.
8. FINISH    run the goal-completion predicate (see per-shape rules below). If the run used repair
             attempts or touched files beyond the final solution, do a **bounded cleanup pass**
             first: inspect the cumulative diff for dead code, scratch files, and debug leftovers
             from abandoned attempts, and remove only what is clearly execution debris and in-scope
             (inspect the diff directly — do not invoke /review or any other skill). Then set
             frontmatter status: complete. Report: units done, evidence, commits made (or "none —
             commit_policy off"), blocked/deferred items, anything cleaned up. OFFER to push (see
             Commit cadence). Do not push unasked. Finally — after the report and push offer — echo
             the top-level verification output and emit the `GOAL-DRIVE COMPLETE` marker as the
             final line of the report (see Terminal markers).
```

Ordering is load-bearing: **verify before ledger, ledger before commit.** Never mark `done`
or commit on intent. **Never satisfy acceptance by weakening the verifier** — deleting or
skipping tests, lowering a threshold, narrowing coverage, disabling a check, or swapping a real
check for a mock — unless the artifact explicitly authorizes it. That games the criterion, not
meets it.

### Per-shape specifics

- **Checklist:** the unit is a *batch* of `batch_size` items; verify and mark each item in the
  batch individually, then (if commit_policy=per_unit) make **one** commit for the batch.
  Goal done = all items `done` AND `done_when` verifies.
- **Phased:** the unit is one phase. Mark its `[state:]` marker + fill its **Evidence:** line.
  Goal done = all phases `done` AND the optional frontmatter `done_when` verifies.
- **Contract (one_shot):** do the goal's work, then verify each `done_when` checkbox — check
  `[x]` + write evidence after the arrow as it passes; a box failing past the repair budget
  gets `<!-- blocked: reason -->` and execution stops. Goal done = every box `[x]`.

## Stop conditions (the only interrupts)

goal-drive is autonomous between these. It stops and hands back only for:

1. **Blocked / unverifiable unit** — acceptance fails past `repair_budget`.
2. **Scope drift** — work surfaces outside the artifact. Append it to `## Emergent` / the
   `emergent` array (default MoSCoW "wont"; schema in `artifact-formats.md`). Continue the
   in-scope work; stop only if the drift blocks progress. Never silently expand scope.
3. **Unclear authority** — an action outside `allow_paths` / `allow_commands`.
4. **One-way door** — an irreversible action in `stop_for` (canonical default:
   `deploy, db_migration, destructive, protected_branch_push, secrets, network_send`).
   Reversible two-way-door actions (working-tree edits, tests, generated files, local commits,
   revertible refactors) proceed without asking.
5. **Explicit user interjection.**

On any of these, print the `GOAL-DRIVE STOPPED: <id> — <reason>: <one line>` marker (canonical form
and reason tags in § Terminal markers) as the first line of the hand-back, before describing what
you need from the user.

Not stop conditions: "a batch finished," "a phase finished," "it's been a while." A boundary
is a checkpoint *of state*, not a request for *permission*. Asking "continue?" at every
boundary is the plan-mode failure mode — don't.

## Authority (single rule)

Operate with the minimum privilege the artifact grants. With an explicit `authority` block,
obey `allow_paths` / `allow_commands` and stop for any class in `stop_for` **plus** the
canonical one-way-door list (the canonical list always applies; an artifact's `stop_for` only
adds to it). **With no `authority` block, use Default authority** (`artifact-formats.md`):
working-tree edits + local commits + commands named in the artifact's acceptance/`done_when`
are allowed; everything else, and every canonical `stop_for` class, requires assent. Announce the assumed defaults in the first status
line. (There is exactly one default — do not gate on a vague "non-trivial.")

## State as a ledger (durability + idempotency)

The artifact must survive a crash or a new session without re-doing or corrupting work:

- **Ledger of fact, not intent.** Persist `done` only after VERIFY passes.
- **Patch in place; never regenerate.** Edit only the unit that changed — preserves a script's
  extra fields and the file's diff history.
- **Stable IDs are idempotency keys.** Re-running skips any unit already `done`. Identical
  re-execution converges; it never duplicates work.
- **Write each state change immediately after VERIFY**, before the next unit — so an
  interruption leaves at most the in-flight unit unrecorded, and the next run re-attempts just
  that one unit.

## Resumption (reconcile before trusting)

On invocation against an artifact with progress:

1. Read the artifact and the last relevant commits.
2. **Reconcile** against repo reality — per shape:
   - **checklist:** for each `done` item, confirm the repo still reflects it; if not, reset
     that item to `pending`. Resume from the first `pending` item.
   - **phased:** scan `[state:]` markers; for each `done` phase confirm the repo still reflects
     it; resume at the first non-`done` phase.
   - **contract:** reconcile each `[x]` `done_when` item; uncheck any whose evidence no longer
     holds; resume from the first unchecked item.
   If a claimed-`done` unit is contradicted by the codebase, **surface the drift and stop** —
   do not silently re-execute. (Same discipline the [[todo]] skill uses for `TODO.md`.)
3. **Blocked units are skipped, not retried** — unless the user signalled the blocker is
   resolved (explicitly, or by editing the unit's state back to `pending`). If the *next* unit
   is `blocked`, stop and report it rather than advancing. Emit a status line noting any
   skipped blocked units so they stay visible.

## Commit cadence

- **Default `none`.** No commits unless the artifact's `commit_policy` is `per_unit`. This
  honors "commit/push only when the user asks" — opting into `per_unit` in the artifact *is*
  that ask. (When goal-elicit sets `per_unit`, it flags this to the user at approval time.)
- **`per_unit`:** one **local** commit per *verified* unit (a checklist batch, or a phase) —
  never per assistant turn. Use the phase's `Commit:` line as the message when present;
  otherwise a short `<scope>: <unit summary>`. goal-drive makes the commit itself (it has
  `Bash` git access).
- **Push is separate and never automatic.** goal-drive does not push and does not invoke the
  push skill. At FINISH (or on request) it **offers** — i.e. tells the user "run `/push` to
  push these N commits." Pushing, remote secret-scan, non-fast-forward handling, and
  atomic-vs-single grouping are the [[push]] skill's job, triggered by the user.

## Cross-session orientation

For a multi-goal / multi-day backlog, append **one pointer line** to a `## Related Goals`
section at the bottom of `TODO.md` **directly** (goal-drive has `Edit`) — do **not** invoke the
[[todo]] skill (it owns a different single-active-task format). Format:
`- <id>: <one-line objective> — see .claude/goals/<id>.<ext> (<done>/<total>)`. Never mirror
per-item state into `TODO.md`.

## Status line format

One compact line per completed unit — observability without ceremony:

```
✓ <unit id/name> — <evidence, e.g. `pytest -q` pass> · next: <unit or "done"> · stops: <active stop-conditions, if any>
```

No prose summaries, no phase tables, no "here's what I did" narration. The artifact and
`git log` are the durable report; the status line is the live ticker; the terminal markers
below are the outer completion / stop signals.

## Terminal markers (transcript evidence)

**This section is the canonical definition of the two terminal markers.** A session-scoped
guardrail — Claude Code's `/goal`, which the user may set between goal-elicit and goal-drive (see
goal-elicit's `references/goal-guardrail.md`) — can only judge the **conversation transcript**: its
evaluator has no file or tool access, so the artifact ledger and a terse status line are invisible
to it. goal-drive emits two machine-stable markers (useful for humans too, whether or not `/goal`
is set); goal-elicit's condition matches them by **prefix**.

- **On completion** — the final line of the FINISH report (printed AFTER the report prose and the
  push offer), only after the goal-completion predicate has actually passed:

  ```
  GOAL-DRIVE COMPLETE: <id> — <n>/<n> <units> verified
  ```

  `<units>` = `done_when` (contract) | `items` (checklist) | `phases` (phased doc). Echo the real
  top-level verification output (command + exit/result, a bounded excerpt) in the report just above
  it. The marker is emitted ONLY from this evidence-gated branch, so it cannot be reached by
  narrating "done" — no passing verification in the transcript ⇒ no marker.

- **On every by-exception stop** (the five Stop conditions above) — as the first line of the
  hand-back:

  ```
  GOAL-DRIVE STOPPED: <id> — <blocked_unit|scope_drift|unclear_authority|one_way_door|user_interjection>: <one line>
  ```

  A goal-completion-predicate failure at FINISH (all units done but the `done_when` predicate
  fails) is also a stop — emit `GOAL-DRIVE STOPPED: <id> — blocked_unit: done_when predicate failed: <detail>`.
  A legitimate stop is a terminal state too; surfacing it lets the `/goal` guardrail clear instead
  of pushing "keep working" against a stop that SHOULD happen.

goal-elicit's `references/goal-guardrail.md` derives its `/goal` condition from these prefixes — if
you change a marker's wording here, mirror it there.
