# atomic-push handoff

Use after execution is complete and every `Done when` item has been verified per the contract's `Verification plan`. `atomic-push` will commit and push.

The contract gates the push: if any `Done when` item is unverified, do not run `atomic-push` yet. Re-run the verification commands first.

## Paste-ready prompt

Substitute `<PATH>` with the actual GOAL.md path.

```text
/atomic-push

Pre-flight: every "Done when" item in <PATH> has been verified per the contract's
"Verification plan" — confirm before staging. If any item is unverified, stop and
report which ones; do not push.

Commit boundaries: one commit per logical change as identified in the contract's
"Scope in" section. Do NOT bundle scope-in items with scope-out cleanup.

Final response: report per the contract's "Final response contract" — which
"Done when" items were verified, with what evidence.
```

## When to use `push` instead

If the contract has a single logical change (most Clear-domain contracts), use `/push` for one bundled commit. Use `/atomic-push` only when the contract's `Scope in` items are genuinely separate logical changes.

## What this handoff does NOT include

- Commit messages. `atomic-push` writes them based on the diff and the contract.
- A push-to-PR step. `atomic-push` pushes to the branch; PR creation is a separate decision.
