# Plan mode handoff

Use when the user wants to decompose the contract into an implementation plan in this same Claude Code session.

Plan mode is downstream of `goal-elicit`. The contract names *what* and *why*; plan mode names *how* — file-by-file changes, sequencing, verification gates.

## Paste-ready prompt

Substitute `<PATH>` with the actual GOAL.md path.

```text
Enter plan mode. Read <PATH> first; treat it as the authoritative source of
intent, scope, constraints, acceptance criteria, and verification. Do NOT
re-elicit the goal. Decompose the contract into a step-by-step implementation
plan. Each plan step should reference the specific "Done when" item(s) it
satisfies and the verification command from "Verification plan" that proves it.
Surface a P0 contract gap if one is discovered — do not silently fill it.
```

## When plan mode would re-open intent

If plan mode finds that the contract is missing a P0 decision (e.g. an architecture choice that wasn't pinned down), it must surface the gap and stop, *not* fill it silently. The user's options:

1. Resume `goal-elicit` to pin the missing decision in the contract.
2. Mark the contract `not_ready_blocked` and add the unknown to `blocking_unknowns`.
3. Override and accept the planning agent's default — record the override as an `assumption` in the contract.

## What this handoff does NOT include

- Implementation steps. Plan mode generates those.
- Verification commands inline. They live in the contract.
