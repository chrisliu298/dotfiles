# Codex /goal handoff

Use when the user wants Codex to autonomously execute the contract via `/goal`.

`/goal` is an execution loop, not a spec validator. The contract handed to it should be already audited (every `done_when` mapped to evidence) — the audit happens in `goal-elicit` Phase 5, not in `/goal`.

## Paste-ready prompt

Substitute `<PATH>` with the actual GOAL.md path, usually `GOAL.md` at the repo root.

```text
/goal Use <PATH> as the sole goal contract for this thread. Implement only items
in "Scope in" — treat "Scope out / non-goals" as anti-goals. Do not call
update_goal "complete" until every checkbox under "Done when" has been verified
against its listed evidence source (command output, file artifact, metric, or
user-observable behavior). Run the commands in "Verification plan" before
marking complete. If you discover a P0 unknown not in the contract, stop and
surface it — do not proceed past the existing scope. When marking complete,
report per "Final response contract".
```

## Optional flags

If the user has set up Codex for long autonomous runs (per `goal-forge`'s config checklist), confirm before invoking:

- `model_reasoning_effort = "high"` for execution
- `plan_mode_reasoning_effort = "xhigh"` for the planning pass
- `approval_policy = "never"` and `sandbox_mode = "danger-full-access"` only in projects explicitly trusted

If the user has not set this up, suggest they run `goal-forge`'s `inspect_codex_config.py` once before kicking off the `/goal` run.

## What this handoff does NOT include

- Codex's own `/goal` budget. The user sets this when invoking `/goal`. Suggest a token budget proportional to the contract's scope.
- Verification commands inline. They live in the contract, not in this prompt — keep the `/goal` prompt thin so Codex reads the contract as the authoritative source.
