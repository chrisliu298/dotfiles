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
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill
---

# goal-drive

Execute a structured goal artifact to **verified done**. The partner of [[goal-elicit]]:
goal-elicit turns a fuzzy ask into a verifiable artifact and stops; goal-drive *consumes*
that artifact (or any conforming one) and drives it. The two compose as a pipeline —
`goal-elicit → artifact → goal-drive` — but goal-drive also runs standalone on a
**bring-your-own** artifact you wrote or generated with a script.

**Runtime portability.** One source of truth for Claude Code, Codex, and Grok — the skill never
detects its runtime. Defaults are agent-neutral. The terminal markers are emitted on every runtime;
Claude Code's `/goal` guardrail consumes them, while Codex has its own native `/goal` executor that
can drive the artifact directly (point it at the file) and Grok has neither — see goal-elicit's
`references/goal-guardrail.md`.

This skill is **modeless on purpose**. There is no "execution mode" you enter or exit. The
artifact on disk is the state; "continue" always means "advance the next unit the artifact
says is unfinished." That single property is what keeps it from becoming a heavyweight plan
mode. (Raskin/Norman on modes; Meyer's Design by Contract; management-by-exception.)

## What it consumes

One artifact, in one of three shapes — full spec in `references/artifact-formats.md`:

- **Contract** `GOAL.md` (or `.goals/<id>.goal.md`) — executable when it carries an `execution:` block; the whole goal is one unit.
- **Checklist** `.goals/<id>.checklist.json` — enumerable items processed in batches.
- **Phased doc** `.goals/<id>.plan.md` — sequential phases with per-phase acceptance.

Existing artifacts under the legacy `.claude/goals/` are still read and driven in place (search `.goals/` first, then `.claude/goals/`); new artifacts use `.goals/`. Full rule: `references/artifact-formats.md` § Where artifacts live.

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
on all-done → run the goal-completion check → report; offer to push (you may invoke a push skill once the user assents — remote push is a one-way door); then echo evidence + the `GOAL-DRIVE COMPLETE: <id> — …` marker as the final line
on exception → print the `GOAL-DRIVE STOPPED: <id> — <reason>` marker first, then hand back
```

The two terminal markers (`GOAL-DRIVE COMPLETE` / `GOAL-DRIVE STOPPED`) make completion and
legitimate stops machine-visible in the transcript on **every runtime** — and are the one signal
Claude Code's optional `/goal` guardrail can read. Always emit them in the exact form
`references/execution-loop.md` § Terminal markers defines (canonical there); they cost nothing when
no guardrail consumes them.

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

goal-drive **may invoke other skills to reach the goal** — e.g. a push/ship skill for verified
commits, a task-tracker, or a multi-model review skill — using whatever your runtime provides (some,
like cross-model review, are Claude-only). Two bounds: an invoked skill must be **in scope and within
the artifact's `authority`** (it may not redefine or expand the goal), and any **one-way-door or
external-dispatch** effect it would cause still needs explicit assent (see Must not). The **one
rail: it never re-elicits** — no interview, no question bank, and it never invokes [[goal-elicit]]
to restart elicitation (run goal-elicit only if the user explicitly asks). And when goal-drive is
**itself running as a dispatched / leaf agent** (e.g. a review/orchestration subagent or relay
peer), it inherits that caller's read-only-leaf contract: it invokes no dispatching skill — anything
that spawns subagents, relays to another model, or runs an orchestration — and takes no side effect
beyond its artifact. It otherwise stays modeless.

- **Own:** the loop, per-unit verification, the state ledger, resumption, the per-unit local
  commit (the when + the message), and the `## Related Goals` pointer line. These are the
  executor's core — goal-drive does them itself rather than delegating.
- **Commits & push:** when `commit_policy: per_unit`, goal-drive makes a **local** commit per
  verified unit itself (via `Bash` git — cheap, single-purpose). At FINISH it may **invoke a push
  skill** to push — but remote push is a one-way door, so it gets the user's go-ahead first (see
  Must not) and never pushes unprompted. Remote secret-scan, non-ff handling, and atomic-vs-single
  grouping are a push skill's job.
- **Cross-session orientation:** for a multi-goal/multi-day backlog, write **one pointer line**
  directly to a `## Related Goals` section at the bottom of `TODO.md` (goal-drive has `Edit`). You
  may invoke a task-tracking skill if the user wants it, but never **mirror per-item goal state**
  into `TODO.md` — it owns a different single-active-task format.
- **Multi-model review:** available if the goal calls for it (or the user asks); not something
  goal-drive reaches for by default.

## Must not

- **Do not re-elicit (the one skill rail).** No interview, no question bank; never invoke
  [[goal-elicit]] to restart elicitation. If the artifact is missing or ambiguous, say "run
  goal-elicit first" or ask the *minimum* to proceed — then stop expanding. Every *other* skill is
  allowed within the artifact's scope/authority — see Composition.
- **Do not enter a mode.** No "execution mode" banner, no enter/exit ceremony, no per-step approval.
- **Do not claim done without evidence.** A unit is `done` only after its acceptance verifies (no verification theater).
- **Do not exceed the contract.** `scope_out`/anti-goals and `authority` remain binding during execution; new ideas go to `## Emergent` (MoSCoW "Won't this time") unless the user promotes them.
- **Do not regenerate the artifact.** Patch state in place so a script's extra fields and the file's history survive.
- **Do not push, deploy, or take any one-way-door action** without explicit assent — even when invoking a skill (e.g. push) that would perform it.

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
