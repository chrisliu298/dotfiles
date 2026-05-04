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

Never *downgrade* domain — claiming "clear" after a 5-round interview is dishonest and will mislead downstream agents.
