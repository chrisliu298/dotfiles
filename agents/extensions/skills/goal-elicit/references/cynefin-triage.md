# Phase 0 — Cynefin triage

Before asking any interview questions, classify the request. The classification controls how aggressive the interview is. Misclassifying *upward* (asking 5 rounds for a rename) is the common failure mode and the one most likely to make this skill annoying.

## Decision tree

Read the seed request. Walk the tree top-down. Stop at the first match.

```
Is the outcome unambiguous AND verifiable AND single-step AND reversible?
├── YES → Clear  (fast lane)
└── NO →
    Is the outcome knowable with a finite amount of investigation,
    even if there are tradeoffs and multiple sub-decisions?
    ├── YES → Complicated  (standard interview, 3–5 rounds)
    └── NO →
        Is the outcome partly emergent? Does success depend on
        learning something the user does not yet know?
        ├── YES → Complex  (exploration interview, 4–6 rounds, contract = next safe probe)
        └── NO →
            Default to Complicated.
```

## What changes per domain

| Domain        | Interview                              | Contract shape                                                                          |
|---------------|----------------------------------------|-----------------------------------------------------------------------------------------|
| Clear         | One confirmation, then write contract. | Full schema, but most sections are 1–3 lines. `rounds_used: 1`. May skip Gherkin if a single command verifies.|
| Complicated   | 3–5 user rounds.                       | Full schema, all sections substantive, at least one Gherkin scenario.                   |
| Complex       | 4–6 user rounds.                       | **Probe contract**, not implementation contract. `Objective` is "learn X by doing Y". `Done when` includes a learning criterion (what fact will be known) and a rollback. |

## Work shape — which artifact to write

Domain sets *interview depth*; **work shape** sets *which artifact* goal-elicit writes. They
are orthogonal. Once scope is clear, ask one extra question (question-bank §0): "Is this one
task, a list of similar items, or a staged build with dependencies?"

| Work shape | Signal | Artifact | goal-drive executes it as |
|---|---|---|---|
| `one_shot` | One deliverable, a small `done_when` set, no enumerable backlog | `GOAL.md` contract | the whole goal, one unit |
| `checklist` | Enumerable, homogeneous items — often script-generatable ("parse into a list first") | `.claude/goals/<id>.checklist.json` | batches of items |
| `phased` | Sequential, heterogeneous stages with distinct per-stage acceptance | `.claude/goals/<id>.plan.md` | one phase at a time |

Rules:

- **Default to `one_shot`.** Promote only on a clear signal. Misclassifying *upward* (a phased
  doc for a two-step task) is the new annoying failure — when in doubt, write the contract.
- Decisive test: *can a script enumerate the units?* → checklist. *Does it need a design with
  staged acceptance?* → phased. Otherwise → contract.
- Work shape only meaningfully ranges over **Complicated** work. **Clear** is essentially
  always `one_shot`; **Complex** stays a probe contract (`one_shot`) — you cannot enumerate
  units you have not discovered yet.
- `one_shot` writes a contract (optionally with `execution.work_shape: one_shot`). `checklist`
  and `phased` write **only** their dedicated artifact — never a companion `GOAL.md`. One goal,
  one artifact. Field semantics: the goal-drive skill's `references/artifact-formats.md`.

goal-elicit still **writes the artifact and stops** regardless of shape. Execution is the
separate goal-drive skill's job; goal-elicit never runs it.

## Worked examples

### Clear

> "Rename the variable `foo` to `user_id` in `src/auth.py`."

Single file. Outcome verifiable by `rg`. Trivially reversible by `git restore`. → Clear. One confirmation ("any callers outside this repo?"), then write the contract.

> "Add a `--dry-run` flag to the existing `cleanup.sh` script that prints what would be deleted without deleting."

Single file. Verifiable by running the script. Reversible. → Clear. One confirmation on dry-run output format, then write.

> "Bump the package version from 0.4.2 to 0.4.3."

Trivial. → Clear. No interview, just confirm and write.

### Complicated

> "I want to add caching to the API but I'm not sure what to cache or how."

Multiple endpoints to consider, multiple cache strategies (memory/redis/CDN), TTL decisions, invalidation strategy, observability needs. All knowable, but the user has tradeoffs to make. → Complicated. Expect 3–5 rounds covering: which endpoints qualify (read-heavy, expensive, idempotent), invalidation strategy, where to put it, observability, deploy plan.

> "Migrate the auth module from session cookies to JWT."

Knowable migration path, but multiple decisions (token storage, refresh strategy, backwards-compat window, key rotation). → Complicated. 4–5 rounds.

> "Refactor the data layer to use the repository pattern."

Knowable but ambiguous scope ("which models?", "what's the cutover?"). → Complicated.

### Complex

> "Help me figure out why our retention is dropping."

Outcome is emergent — until you look at the data, you don't know whether the answer is product, marketing, technical, or seasonal. → Complex. The contract should describe the next probe (e.g. "cohort decay analysis on the last 6 months of signups, segmented by acquisition channel"), the learning criterion (what would change the next decision), and a rollback (none needed for a read-only probe).

> "Optimize this codebase."

No verifiable target, no scope, no metric. → Complex. Either drag the user to a Complicated reformulation ("optimize *what* — startup time, memory, build speed?"), or write a probe contract: "instrument the three suspected bottlenecks for one week, then decide".

> "Build a system that can autonomously fix bugs."

Outcome is emergent and the path is unknown. → Complex. Probe contract: "build the smallest end-to-end loop on a single bug class, measure success rate, decide whether to scale".

## When the classification was wrong

If you classified Clear and find yourself asking a third question, escalate to Complicated and continue. Update `cynefin_domain` in the frontmatter.

If you classified Complicated and the user keeps saying "I don't know" or every answer opens a new dimension you didn't expect, escalate to Complex and reframe the contract as a probe.

Never *downgrade* domain — claiming "clear" after a 5-round interview is dishonest and will mislead whoever reads the contract.
