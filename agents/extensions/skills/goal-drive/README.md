# goal-drive

> Drive an existing goal artifact — `GOAL.md`, a JSON checklist, or a phased doc — to **verified
> done**. A modeless loop: do the next unit, verify its acceptance, ledger it, optionally commit,
> repeat — stopping only by **exception**.
>
> **`SKILL.md` is the authoritative spec** — this README is the picture. One source of truth for
> **Claude Code, Codex, and Grok**. The execution partner of [goal-elicit](../goal-elicit/).

---

## The idea — modeless execution, supervised by exception

There is no "execution mode" to enter or exit. **The artifact on disk is the state**; "continue"
always means "advance the next unit the artifact says is unfinished." That single property is what
keeps it from becoming a heavyweight plan mode. (Raskin/Norman on modes; Meyer's Design by Contract;
management-by-exception.)

```
 artifact  (GOAL.md / .goals/<id>.*)
     │
     ▼
 load → reconcile against the repo  (trust only verified facts)
     │
     ▼
 ┌──────────────── the loop ─────────────────┐
 │ while units remain AND no exception:       │
 │   select  next pending unit                │
 │   announce  (declarative, not a permission)│
 │   act       (reversible · in-scope · in-authority)
 │   verify    against the unit's acceptance  │
 │   ledger    → patch the artifact in place  │
 │   commit    (optional: one local, per unit)│
 └─────────────────────┬─────────────────────┘
        ┌──────────────┴───────────────┐
        ▼                               ▼
    all done                          exception
 GOAL-DRIVE COMPLETE: <id> — n/n   GOAL-DRIVE STOPPED: <id> — <reason>
```

## What it consumes — three shapes (or bring-your-own)

| Shape | File | Unit of work |
|---|---|---|
| **Contract** | `GOAL.md` / `.goals/<id>.goal.md` | the whole goal (its `done_when` items are sub-units) |
| **Checklist** | `.goals/<id>.checklist.json` | a batch of items |
| **Phased doc** | `.goals/<id>.plan.md` | one phase |

Legacy `.claude/goals/` artifacts are still read and driven in place (new ones use `.goals/`). A
hand-written or script-generated file works too, as long as it meets the bring-your-own conformance
in `references/artifact-formats.md`. goal-drive owns the loop and the state — it never *generates*
the work list.

## Checkpoints are by exception, not by schedule

After the one approval that already happened (the artifact itself), goal-drive runs autonomously. It
stops and asks **only** for:

1. a **blocked** unit (acceptance fails past the repair budget),
2. **scope drift** (work outside the artifact → appended to `## Emergent`, default "won't"),
3. **unclear authority** (an action outside `allow_paths` / `allow_commands`), or
4. a **one-way door** (deploy, db migration, destructive op, protected-branch push, secrets,
   external send).

It does **not** ask "continue?" at every batch or phase boundary — the state file and `git log` are
the progress report.

## Terminal markers & guardrails

Every run ends with a machine-stable, human-readable marker — `GOAL-DRIVE COMPLETE: <id>` or
`GOAL-DRIVE STOPPED: <id> — <reason>` — emitted on **every runtime**. Claude Code's optional `/goal`
guardrail reads these to keep a session working until done; Codex has its own native `/goal`
executor (point it at the artifact file); Grok has neither. See goal-elicit's
`references/goal-guardrail.md`.

## Composition — owns the loop, may delegate the rest

goal-drive owns its loop, per-unit verification, the state ledger, resumption, and its own local
commits. It **may invoke other skills to reach the goal** — a push/ship skill, a task-tracker, a
multi-model review skill — within the artifact's scope and authority (some, like cross-model review,
are Claude-only). The **one rail: it never re-elicits** (no interview; run goal-elicit only if you
ask). One-way-door and external-dispatch actions still require explicit assent, even via a skill.

## Files

| File | What |
|---|---|
| `SKILL.md` | the authoritative spec |
| `references/artifact-formats.md` | the 3 artifact shapes, bring-your-own conformance, and the authority model |
| `references/execution-loop.md` | the loop in full: stop conditions, ledger/idempotency/resumption, commit cadence, terminal markers |

## Invocation

`/goal-drive` on Claude Code (optionally under a `/goal` guardrail); invoke the **goal-drive** skill
by name on Codex (or use Codex's `/goal` pointed at the artifact). Triggers: "drive this", "execute
this plan/checklist", "run the phases", "carry this to done".
