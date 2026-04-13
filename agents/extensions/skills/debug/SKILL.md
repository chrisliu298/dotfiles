---
description: |
  Structured debugging: investigate root cause before proposing any fix.
  Use when encountering bugs, test failures, flaky tests, unexpected behavior,
  build failures, or performance regressions. Also trigger when the user says
  "debug this", "investigate", "why is this failing", "what's wrong", "figure
  out why", "it broke", or invokes "debug". Especially important after a fix
  attempt that didn't work — stop guessing and follow the process. Do NOT use
  for feature implementation or code review.
user-invocable: true
allowed-tools: Bash, Read, Edit, Grep, Glob
effort: high
---

# Systematic Debugging

Find the root cause before attempting any fix. Symptom-level patches waste time, mask real issues, and introduce new bugs.

The instinct to "just try something" is strongest under pressure — and that's exactly when it's most expensive. A systematic 15-minute investigation beats 2 hours of guess-and-check.

**Write everything to `DEBUG.md`.** Observations, hypotheses, evidence, experiment results, and root cause all go in this file. Context compaction will eat reasoning that only lives in the conversation — DEBUG.md is the durable record. Create it at the repo root when Phase 1 begins.

## Phase 1: Investigate

Complete this phase before proposing any fix.

### Read the error carefully

Read the full stack trace — don't stop at the first frame. Note line numbers, file paths, error codes. Error messages often contain the answer.

### Check the environment

Before diving into code, verify: correct dependency versions installed? Required services running? Environment variables set? The right branch checked out? Many "bugs" are environment mismatches.

### Reproduce and minimize

Can you trigger the bug reliably? Reduce to the smallest failing test, command, or script. If it's intermittent, gather timestamps, inputs, and environment details — intermittent bugs have deterministic causes (usually race conditions, state pollution, or environment variance). For flaky tests, run the failing test in isolation first; if it passes alone but fails in the suite, the cause is usually shared state between tests.

Record all findings in `DEBUG.md` under `## Observations` — exact error messages, stack traces, environment details, what works vs. what doesn't.

### Check recent changes

```bash
git log --oneline -10
git diff HEAD~3
```

Recent changes are often the fastest place to start. But note: sometimes a recent change merely exposes a latent bug. Check whether the bug could have occurred before the change.

### Trace the data flow

When the error is deep in a call stack, trace backward: where does the bad value originate? What called this function with the bad input? Keep tracing upstream until you find where correct data becomes incorrect. Fix at the source, not at the symptom.

### Multi-component systems

When the system spans multiple layers, add temporary diagnostic logging at each boundary before guessing which layer is broken. One diagnostic run that reveals the failing boundary is worth more than three blind fix attempts. For timing-dependent bugs, use condition-based waits or explicit synchronization rather than arbitrary sleeps.

### Compare with working code

Find similar working code in the same codebase. List every difference between working and broken, however small. Check which assumptions the broken code makes about its dependencies and environment.

## Phase 2: Hypothesize and test

### Form one hypothesis

State it clearly: "X is causing this because Y." Be specific — vague hypotheses ("something's wrong with the config") lead to vague fixes. Keep multiple candidate hypotheses in mind, but test one change at a time. Write each hypothesis to `DEBUG.md` under `## Hypotheses` with supporting evidence, conflicting evidence, and the planned experiment.

### Test minimally

Make the smallest possible change to test your hypothesis. One variable at a time. Don't fix multiple things at once — you won't know which change actually helped.

### Evaluate

- Hypothesis confirmed → Phase 3
- Hypothesis rejected → **revert the change**, record the rejection and evidence in `DEBUG.md`, form a new hypothesis based on what you learned
- Same direction fails twice → the hypothesis is dead, move on
- Don't stack more changes on top of a failed attempt

## Phase 3: Fix

### Report diagnosis first

Before writing any fix, summarize: root cause, evidence, rejected hypotheses, and why the chosen fix addresses the source rather than the symptom. Write the root cause to `DEBUG.md` under `## Root Cause` and the fix rationale under `## Fix`. This prevents "investigated" claims without actual investigation.

### Implement the fix

1. **Write a failing test** that reproduces the bug (if the codebase has a test framework; otherwise, a minimal reproduction script)
2. **Implement a single fix** addressing the root cause — one change, no "while I'm here" improvements
3. **Verify** — test passes, no regressions, issue actually resolved
4. **Remove diagnostic instrumentation** — temporary logging or probes must be cleaned up

If the `tdd` skill is active, Phase 3 follows the TDD cycle: the failing test is your RED step, the fix is GREEN, then REFACTOR.

### When fixes keep failing

If you've made multiple fix attempts without gaining new evidence each time, the problem is likely architectural, not a surface bug. Signals: each fix reveals a new issue in a different place, fixes require major refactoring, each fix creates new symptoms elsewhere.

Stop fixing and discuss with the user. This is not failure — it's recognition that incremental patches won't work and the approach needs rethinking.

## Gotchas

These are the real failure points when debugging with an AI agent:

- **Proposing fixes during Phase 1.** The strongest instinct is to suggest a solution immediately after reading an error message. Resist this — finish the investigation first. An obvious-looking fix that addresses a symptom instead of the root cause costs more time than it saves.
- **"It's probably X" without evidence.** Intuition is useful for forming hypotheses (Phase 2), not for skipping investigation (Phase 1). Even when you're 90% sure, verify before fixing.
- **Not reverting failed attempts.** After a hypothesis is disproven, revert the change before trying the next one. Stacking failed fixes corrupts the debugging state and makes it impossible to isolate what's happening.
- **Changing multiple things at once.** Can't isolate what helped and what hurt. One change at a time.
- **Fixing at the point of failure instead of the source.** A NullPointerException on line 42 means something upstream produced null. Adding `if (x == null) return` on line 41 silences the error but doesn't fix the bug. Trace backward to where the null originates.
- **Not reducing to a minimal reproduction.** Without a minimal repro, you debug the entire system at once. Shrink the failing case before expanding the investigation.
- **Treating "works sometimes" as fixed.** Intermittent failures still have causes. If you can't explain the variance, you haven't finished debugging.
- **Leaving diagnostic instrumentation behind.** Temporary logging or probes added during investigation must be removed before closing the task.
