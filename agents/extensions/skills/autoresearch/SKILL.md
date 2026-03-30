---
name: autoresearch
user-invocable: true
description: >
  Autonomous experiment loop faithful to Karpathy's autoresearch. Set up a branch,
  establish a baseline, then loop forever: edit, commit, run, measure, keep or revert.
  Use when asked to "run autoresearch", "optimize X in a loop", or "start experiments".
effort: max
---

# Autoresearch

You are a completely autonomous researcher. Try things out. If they work, keep. If they don't, discard. Never stop.

Based on Karpathy's autoresearch (github.com/karpathy/autoresearch). Generalized to work with any optimization target. The original `program.md` is in `references/` — read it when you need to check the source principles.

## Setup

Work with the user to establish these, then start:

1. **Metric**: What to optimize, and the direction (lower/higher is better). Ask — do not guess direction.
2. **Command**: The shell command that runs one experiment (e.g. `python train.py`, `make bench`).
3. **Metric extraction**: How to get the primary metric from output (e.g. `grep "^val_bpb:" run.log`). Also specify how to extract resource usage (peak memory, runtime) if the command reports it. If it doesn't, note what monitoring is available (e.g. `/usr/bin/time -v`, `nvidia-smi`).
4. **Comparison protocol**: What stays fixed across experiments so "better" is meaningful — evaluation harness, time/work budget, dataset, seed policy. If the command runs for a fixed time budget, all experiments are directly comparable regardless of what you change.
5. **Files in scope**: Which files you may edit. Default to the smallest coherent set — one file is ideal. Everything else is read-only. Expanding scope requires explicit justification.
6. **Constraints**: Hard rules (no new deps, tests must pass, memory limit, etc.). Default: no new dependencies, do not modify evaluation/data code.
7. **Guard** (optional): A command that must *always* pass, separate from the metric. Protects existing behavior while optimizing. E.g. `npm test`, `pytest`, `cargo test`. If not specified, no guard is used.

Auto-detect what you can from the repo (look for run scripts, Makefiles, pyproject.toml). Infer defaults aggressively and only ask about genuinely unresolved choices. Confirm in one round — then go.

Then:

1. `git checkout -b autoresearch/<tag>` from the main branch. Propose a tag based on today's date (e.g. `mar13`). Branch must not already exist.
2. Read every in-scope file AND all relevant read-only files (evaluation code, data loading, configs, README). Understand the full system — not just the parts you edit.
3. **Preflight.** Verify prerequisites before wasting the baseline run: required data/artifacts exist, command is available, output path is writable, any required hardware/tooling is present. If something is missing, tell the user immediately.
4. Add `results.tsv` and `run.log` to `.gitignore` if not already present. Commit the `.gitignore` change.
5. Create `results.tsv` with the header row (see Logging). Do NOT commit this file.
6. Run the **baseline**: execute the command as-is, no modifications. Record it in `results.tsv` as experiment #0.
7. Write `autoresearch.md` (see below). Commit it.
8. Start the loop immediately.

### `autoresearch.md`

Recovery document so a fresh agent can continue the loop. Keep it concise.

```
# Autoresearch: <goal>

## Objective — what we're optimizing and why
## Metric — name, unit, direction
## Command — exact shell command
## Metric Extraction — exact grep/parse command (primary metric + resource metrics)
## Comparison Protocol — what stays fixed (time budget, evaluator, dataset, seed)
## Files in Scope — each file, one-line note (smallest coherent set)
## Off Limits — what must not be touched
## Constraints — hard rules
## Guard — command that must always pass (or "none")
## What's Been Tried — key wins, dead ends, insights (update every ~5 experiments)
```

## The Loop

**LOOP FOREVER** (unless bounded by `loop N`). Do NOT ask "should I continue?", "is this a good stopping point?", or any variation. The user may be asleep or away from their computer. They expect you to work indefinitely until manually stopped.

When bounded via `loop N autoresearch`, run exactly N iterations, then print a final summary and stop.

Maximize throughput. Planning and editing time should be a small fraction of run time. For 5-minute runs, target ~10 experiments/hour.

Each iteration, in this order:

1. **Check git state.** Note the current branch and commit. Working tree should be clean.
2. **Plan.** One hypothesis, one line. Everything in scope is fair game — architecture, algorithms, hyperparameters, batch size, model size, optimizer, scheduling, radical restructuring. Do not over-deliberate.
3. **Edit.** Modify only in-scope files.
4. **Commit.** `git add <files> && git commit -m "<description>"` — commit BEFORE running (so the change is recorded even if the experiment crashes or the agent is interrupted).
5. **Run.** `<command> > run.log 2>&1` — redirect everything. Do NOT use `tee`. Do NOT let output flood your context.
6. **Extract.** Run the extraction command. If it produces no output, the run crashed or did not complete — `tail -n 50 run.log` for the stack trace. Also extract resource metrics (memory, runtime) if available.
7. **Record.** Append the result to `results.tsv`. Do NOT commit `results.tsv`.
8. **Guard.** If a guard command was defined, run it now (only when the metric improved — no point guarding a discard). If the guard fails, the optimization broke existing behavior. Rework: revert (`git reset --hard HEAD~1`), re-implement the same idea differently to avoid the regression, commit, re-run verify + guard. Max 2 rework attempts. If it still fails, discard. **Never modify guard/test files** — always adapt the implementation.
9. **Decide.** Compare against the current best (find the last `keep` row in `results.tsv`, or the baseline if no improvements yet):
   - **Improved** (and guard passed, if any) → `keep`. The commit stays. Branch advances.
   - **Equal or worse** → `discard`. `git reset --hard HEAD~1` to revert. Exception: if the metric is equal but the code is meaningfully simpler, treat as `keep` per the simplicity criterion.
   - **Improved but guard failed** (after rework attempts) → `discard`. Log reason.
   - **Crash** → Triage first. Is the failure (a) a trivial bug — typo, missing import, shape mismatch? Fix and retry, max 1-2 attempts. (b) An environment issue — wrong path, missing asset? Remediate explicitly. (c) Idea-invalidating — OOM on a design that inherently needs 2x memory, algorithm that can't converge in the time budget? Skip immediately, don't waste retries. Log as `crash`, `git reset --hard HEAD~1`, move on.
   - **Near-threshold win** → If the improvement is small enough that it could be noise, re-run to confirm or document why you believe the gain is real before keeping.
10. **Report.** Every 5 iterations, print a one-line progress summary: `=== Iteration N: metric at X.XX, K keeps / D discards / C crashes ===`
11. **Repeat.** Go to step 1.

### Bounded Loop Summary

When running under `loop N`, print this after the final iteration:

```
=== Autoresearch Complete (N iterations) ===
Baseline: <value> → Best: <value> (<delta>)
Keeps: X | Discards: Y | Crashes: Z
Best experiment: #<n> — <description>
```

### Timeout

If a run exceeds 10 minutes (or a user-specified limit), kill it. Record as `crash`. Revert.

### Resource Usage

Memory and other resource metrics are soft constraints. Some increase is acceptable for meaningful metric gains, but usage should not blow up dramatically. Track resource usage in `results.tsv` and factor it into keep/discard decisions alongside the simplicity criterion.

### Simplicity Criterion

Apply this to every keep/discard decision. The threshold for "small improvement" depends on your metric's noise and scale — near-threshold wins should clearly exceed run-to-run variance to justify added complexity.

- **Small improvement + ugly complexity** (e.g. tiny gain + 20 lines of hacky code) → probably discard. The complexity is not worth it.
- **Removing code + equal or better performance** → definitely keep. This is a simplification win.
- **Equal metric + simpler code** → keep. Simplicity has intrinsic value.
- **Large improvement** justifies added complexity. Use judgment on the threshold.

### When Stuck

If you've reverted 3+ experiments in a row, your current strategy isn't working. Step back and change approach entirely:

- Re-read the source files with fresh eyes. What is the code *actually* doing?
- Read papers or references relevant to the optimization target.
- Combine elements from previous near-misses.
- Try radical structural changes, not incremental parameter tweaks.
- Reason about what the execution environment is doing (memory access, compute bottlenecks, cache behavior).
- As a last resort, rewind to an earlier successful commit (`git log` to find it, `git reset --hard <hash>`) and try a completely different direction. This discards all intermediate commits. Use very sparingly — almost never.

Remember: everything in scope is fair game. Do not limit yourself to parameter tuning. Architecture changes, algorithm swaps, removing entire subsystems, rewriting from scratch — all are valid experiments.

**NEVER give up. NEVER ask the user for ideas. Think harder.**

### What You Cannot Do

- Edit files outside scope.
- Install new packages or dependencies.
- Modify the evaluation or measurement harness.
- Commit `results.tsv` or `run.log`.
- Stop to ask the user for permission.

## Logging

`results.tsv` — TAB-separated (NOT CSV — commas break in descriptions). 5 columns:

```
commit	metric	memory_gb	status	description
```

- **commit**: short git hash (7 chars)
- **metric**: primary metric value. Use `NA` for crashes.
- **memory_gb**: peak memory in GB, rounded to .1f. Use `0.0` if unavailable or crash.
- **status**: `keep`, `discard`, or `crash` — `status` is authoritative for crash detection, not the metric value.
- **description**: short text of what this experiment tried

Example:

```
commit	metric	memory_gb	status	description
a1b2c3d	0.997900	44.0	keep	baseline
b2c3d4e	0.993200	44.2	keep	increase LR to 0.04
c3d4e5f	1.005000	44.0	discard	switch to GeLU activation
d4e5f6g	NA	0.0	crash	double model width (OOM)
```

**Do NOT commit `results.tsv`.**

## Resuming

If `results.tsv` and an `autoresearch/*` branch already exist:

1. `git checkout autoresearch/<tag>` — switch to the existing experiment branch.
2. Read `autoresearch.md` for context.
3. Read `results.tsv` — only the last `keep` row to find the current best, not the entire file.
4. Read `git log --oneline -20` for recent commits.
5. Read all in-scope files.
6. Continue the loop. Do not re-run the baseline. Do not ask questions.

## User Messages

If the user sends a message while an experiment is running, finish the current experiment first. Incorporate their direction in the next iteration. Do not stop mid-experiment.

## NEVER STOP.

Once the loop has begun, do NOT pause to ask the human if you should continue. Do NOT ask "should I keep going?" or "is this a good stopping point?" or summarize and ask for next steps. The human might be asleep, or gone from a computer and expects you to continue working *indefinitely* until you are manually stopped. If each experiment takes N minutes, you should complete dozens or hundreds of experiments in an overnight session.

**Unbounded mode** (default): The loop runs until the human interrupts you, period.

**Bounded mode** (`loop N autoresearch`): Run exactly N iterations, print the final summary (see Bounded Loop Summary), then stop.
