# subagent-executor handoff

Use when the contract has multiple disjoint scope slices that can be executed in parallel by fresh subagents.

`subagent-executor` works best for tasks with **disjoint write scopes** — slices that won't step on each other's files. If the contract is tightly coupled (every change touches every other), recommend a single executor instead.

## Paste-ready prompt

Substitute `<PATH>` with the actual GOAL.md path. Replace the slice list with the actual partitioning from the contract.

```text
/subagent-executor

Source contract: <PATH>

Slices:
1. <slice name> — files in scope: <list>; "Done when" items: [N1, N2]
2. <slice name> — files in scope: <list>; "Done when" items: [N3, N4]
3. <slice name> — files in scope: <list>; "Done when" items: [N5]

Each subagent reads <PATH> for shared constraints, scope-out, anti-goals, and
verification commands. The dispatcher gates merging each slice on its
"Done when" items being verified per the contract's "Verification plan".
Do NOT have any subagent expand its slice's scope — surface a contract
amendment request instead.
```

## Choosing slices

Good slice signals:

- Each slice owns a disjoint set of files.
- Each slice's `Done When` items are verifiable independently.
- Slices share constraints (style, stack) but not implementation details.

Bad slice signals:

- One slice writes a function that another slice consumes (sequential, not parallel).
- Slices share mutable state in the same file.
- Verification of slice A depends on slice B already being merged.

When the contract isn't naturally sliceable, hand off to plan mode or `/goal` instead.

## What this handoff does NOT include

- Per-subagent prompts. `subagent-executor` generates those from the contract.
- Review-gate criteria. Use the contract's `Done when` and `Verification plan`.
