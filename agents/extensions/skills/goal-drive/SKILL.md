---
name: goal-drive
description: |
  Drive an existing goal artifact to verified done — a GOAL.md contract, a JSON checklist,
  or a phased design doc (produced by goal-elicit, or hand/script-written). Executes
  modelessly: process the next unit, verify acceptance, update state, optionally commit,
  repeat — stopping only on exceptions (blocked unit, scope drift, unclear authority, an
  irreversible action). Use for "drive this", "execute this plan/checklist", "process this
  in batches", "run the phases", "carry this to done". Does NOT interview — if the goal is
  unclear or no artifact exists, run goal-elicit first. Skip for one-off edits and factual
  questions.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# goal-drive

Execute a structured goal artifact to **verified done**. The partner of [[goal-elicit]]:
goal-elicit turns a fuzzy ask into a verifiable artifact and stops; goal-drive *consumes*
that artifact (or any conforming one) and drives it. The two compose as a pipeline —
`goal-elicit → artifact → goal-drive` — but goal-drive also runs standalone on a
**bring-your-own** artifact you wrote or generated with a script.

This skill is **modeless on purpose**. There is no "execution mode" you enter or exit. The
artifact on disk is the state; "continue" always means "advance the next unit the artifact
says is unfinished." That single property is what keeps it from becoming a heavyweight plan
mode. (Raskin/Norman on modes; Meyer's Design by Contract; management-by-exception.)

## What it consumes

One artifact, in one of three shapes — full spec in `references/artifact-formats.md`:

- **Contract** `GOAL.md` (or `.claude/goals/<id>.goal.md`) — executable when it carries an `execution:` block; the whole goal is one unit.
- **Checklist** `.claude/goals/<id>.checklist.json` — enumerable items processed in batches.
- **Phased doc** `.claude/goals/<id>.plan.md` — sequential phases with per-phase acceptance.

A hand-written or script-generated file is valid as long as it meets the **bring-your-own
conformance** in `references/artifact-formats.md`. goal-drive never *generates* the work list
— it owns the loop and the state updates, not the enumeration.

## The loop (overview)

Detailed rules — stop conditions, authority, state-ledger discipline, idempotency,
resumption, commit cadence, status format — are in `references/execution-loop.md`. Read it
before driving. The shape:

```
load artifact → reconcile against the repo (trust only verified facts)
while unverified units remain AND no exception:
    unit  = next pending  (checklist: a batch of batch_size | phased: first non-done phase | contract: the goal)
    announce the next unit in 1–3 lines (declarative — not a permission request)
    act    within the artifact's authority (reversible / in-scope only)
    verify against the unit's acceptance
    ledger: flip to done with evidence — patch the artifact in place (never regenerate)
    if commit_policy == per_unit → one local git commit for this verified unit
    emit a compact status line: unit · evidence · next · active stop-conditions
on all-done → run the goal-completion check → report; OFFER to push (tell the user to run /push)
```

## Checkpoints are by exception, not by schedule

After the one approval that already happened (the artifact itself), goal-drive runs
autonomously. It **stops and asks only** when:

1. a unit is **blocked** or its acceptance can't be verified within the repair budget,
2. it discovers work **outside the artifact's scope** (append it to an `## Emergent` section, default "Won't this time"; stop only if it blocks progress),
3. **authority is unclear** (an action outside `allow_paths`/`allow_commands`), or
4. the next action is a **one-way door** — irreversible or costly-to-reverse (deploy, db migration, destructive op, protected-branch push, secrets, sending external messages).

It does **not** ask "continue?" at every batch or phase boundary. That per-step prompting is
exactly the plan-mode heaviness to avoid; the state file and `git log` are the progress
report. (See `execution-loop.md` for the full stop/authority rules.)

## Composition — own vs delegate

- **Own:** the loop, per-unit verification, the state ledger, resumption, the per-unit local
  commit (the when + the message), and the `## Related Goals` pointer line.
- **Commits:** when `commit_policy: per_unit`, goal-drive makes a **local** commit per verified
  unit itself (via `Bash` git — cheap, single-purpose). It does **not** push and does **not**
  invoke the [[push]] skill. At FINISH it **offers** — tells the user to run `/push`. Remote
  push, secret-scan, non-ff handling, and atomic-vs-single grouping are `push`'s job, triggered
  by the user.
- **Cross-session orientation:** for a multi-goal/multi-day backlog, write **one pointer line**
  directly to a `## Related Goals` section at the bottom of `TODO.md` (goal-drive has `Edit`).
  Do **not** invoke the [[todo]] skill — it owns a different single-active-task format. Never
  mirror per-item state into `TODO.md`.
- **Multi-model review** ([[relay]]/[[prism]]): not goal-drive's job — if the user wants it,
  they invoke it separately. goal-drive does not.

## Must not

- **Do not re-elicit.** No interview, no question bank. If the artifact is missing or
  ambiguous, say "run goal-elicit first" or ask the *minimum* to proceed — then stop expanding.
- **Do not enter a mode.** No "execution mode" banner, no enter/exit ceremony, no per-step approval.
- **Do not claim done without evidence.** A unit is `done` only after its acceptance verifies (no verification theater).
- **Do not exceed the contract.** `scope_out`/anti-goals and `authority` remain binding during execution; new ideas go to `## Emergent` (MoSCoW "Won't this time") unless the user promotes them.
- **Do not regenerate the artifact.** Patch state in place so a script's extra fields and the file's history survive.
- **Do not invoke another skill.** goal-drive owns its loop, makes its own local commits, and writes its own `## Related Goals` pointer line. It never invokes goal-elicit, push, todo, relay, or prism — it *offers* `/push` and lets the user trigger it.
- **Do not push, deploy, or take any one-way-door action** without explicit assent.

## Resumption

If invoked on an artifact that already has progress: read it, **reconcile against the repo**
(does the codebase actually reflect the claimed-`done` units?), report any drift instead of
silently re-running, then continue from the first `pending` unit. Resumption derives the next
unit from recorded verified facts (checklist item state / phase `[state:]` markers / contract
`done_when` checkboxes), never from a fragile "currently on step N" pointer. **Blocked units
are skipped** unless the user flips them back to `pending`; if the next unit is itself blocked,
stop and report it. Full per-shape rules: `references/execution-loop.md`.

## Files in this skill

- `SKILL.md` — this file.
- `references/artifact-formats.md` — the 3 artifact shapes goal-drive consumes (the shared contract with goal-elicit) + bring-your-own conformance.
- `references/execution-loop.md` — the loop in full: stop conditions, authority/least-privilege, state-ledger + idempotency + resumption, commit cadence, status format.

Read the references when you need them, not all up front.
