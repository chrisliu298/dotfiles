# Autoresearch

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that turns your agent into an autonomous researcher.**

> *You push start, go to sleep. You wake up to a branch full of winning experiments and a log of everything that was tried.*

Based on Karpathy's [autoresearch](https://github.com/karpathy/autoresearch). Generalized to work with any optimization target, any codebase, any metric.

Invoke with `/autoresearch` or ask your agent to "run autoresearch", "optimize X in a loop", or "start experiments".

## Table of Contents

- [Why](#why)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Usage](#usage)
- [The Loop](#the-loop)
- [Logging](#logging)
- [Resuming](#resuming)
- [Safety](#safety)
- [Contributors](#contributors)

---

## Why

Running experiments manually is slow. You change a hyperparameter, run the script, wait, check the result, decide whether to keep it, and repeat. Most of that is mechanical.

Autoresearch makes your agent do it all:

- **Autonomous iteration** — the agent runs experiments indefinitely without asking for permission or guidance
- **Automatic version control** — every experiment is committed before running; improvements advance the branch, failures are reverted
- **Structured logging** — every result is recorded in a TSV with commit hash, metric, memory, status, and description
- **Smart keep/discard** — the agent weighs metric improvement against code complexity, preferring simplicity

### Why not just write a script?

A hyperparameter sweep script explores a predefined grid. Autoresearch explores the *idea space* — architecture changes, algorithm swaps, radical restructuring, insights from reading the code with fresh eyes. Each iteration is a creative decision, not a grid point.

---

## How It Works

```
┌─────────────────────────────────────────────┐
│  1. Setup: branch, baseline, results.tsv    │
├─────────────────────────────────────────────┤
│  2. Loop (forever):                         │
│     plan → edit → commit → run → measure    │
│         ↓               ↓                   │
│     improved?        equal/worse?           │
│         ↓               ↓                   │
│       keep            revert                │
│     (branch           (git reset            │
│      advances)         --hard HEAD~1)       │
├─────────────────────────────────────────────┤
│  3. results.tsv tracks everything           │
└─────────────────────────────────────────────┘
```

The agent works on a dedicated `autoresearch/<tag>` branch. The branch HEAD is always the best result so far. The `results.tsv` file (untracked) is the full experiment history.

---

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/autoresearch.git ~/.claude/skills/autoresearch
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/autoresearch.git ~/.codex/skills/autoresearch
```

---

## Usage

Tell your agent what to optimize:

> "Run autoresearch on this training script — optimize val_bpb, lower is better"

> "Start experiments to minimize inference latency in bench.py"

> "Optimize the sorting benchmark, higher throughput is better"

The agent will:

1. Confirm the **metric**, **command**, **metric extraction**, **files in scope**, and **constraints** with you in one round
2. Create an `autoresearch/<tag>` branch
3. Run the baseline
4. Start the loop — and never stop

### What you provide

| Parameter | Example |
|-----------|---------|
| Metric + direction | `val_bpb`, lower is better |
| Run command | `python train.py`, `make bench` |
| Metric extraction | `grep "^val_bpb:" run.log` |
| Files in scope | `train.py` (everything else read-only) |
| Constraints | No new deps, don't modify eval code |
| Guard (optional) | `npm test`, `pytest` — must always pass |

The agent auto-detects what it can from the repo and proposes defaults.

### Guard

The guard is an optional safety net — a command that must always pass alongside metric improvements. It prevents optimizing a metric while accidentally breaking existing behavior.

```
Metric: inference latency (lower is better)
Command: python bench.py
Guard: pytest tests/
```

If the metric improves but the guard fails, the agent reworks the implementation (up to 2 attempts) to avoid the regression. Guard/test files are never modified.

---

## The Loop

Each iteration follows a strict sequence:

1. **Check git state** — clean working tree, note current branch and commit
2. **Plan** — choose what to try next (architecture, algorithms, hyperparameters, radical changes)
3. **Edit** — modify only in-scope files
4. **Commit** — `git commit` before running (so the experiment is recorded even if it crashes)
5. **Run** — `command > run.log 2>&1` (output stays out of agent context)
6. **Extract** — parse the metric from `run.log`
7. **Record** — append to `results.tsv`
8. **Guard** — if defined, verify existing behavior still passes
9. **Decide**:
   - **Improved** (and guard passed) — keep the commit, branch advances
   - **Equal or worse** — `git reset --hard HEAD~1`
   - **Improved but guard failed** — rework or discard
   - **Crash** — fix if trivial, otherwise revert and move on
10. **Report** — every 5 iterations, print a progress summary

### Simplicity criterion

Not all improvements are worth keeping:

- **Small gain + ugly complexity** (0.1% better + 20 lines of hacks) — probably discard
- **Removing code + equal or better** — definitely keep
- **Near-zero gain + simpler code** — keep (simplicity has intrinsic value)
- **Large improvement** — justifies added complexity

### When stuck

The agent does not give up. It re-reads source files, looks for patterns in past experiments, combines near-misses, tries radical structural changes, and reasons about execution bottlenecks. As a last resort, it rewinds to an earlier successful commit and tries a different direction.

### Bounded loops

By default, autoresearch loops forever. Use `/loop N /autoresearch` to run exactly N iterations then stop with a summary:

```
=== Autoresearch Complete (25 iterations) ===
Baseline: 0.9979 → Best: 0.9712 (-0.0267)
Keeps: 8 | Discards: 15 | Crashes: 2
Best experiment: #14 — switch to rotary embeddings
```

### Timeout

Runs exceeding 10 minutes (or a user-specified limit) are killed and recorded as crashes.

---

## Logging

`results.tsv` — tab-separated, 5 columns:

```
commit	metric	memory_gb	status	description
a1b2c3d	0.997900	44.0	keep	baseline
b2c3d4e	0.993200	44.2	keep	increase LR to 0.04
c3d4e5f	1.005000	44.0	discard	switch to GeLU activation
d4e5f6g	0.000000	0.0	crash	double model width (OOM)
```

The file is never committed — it stays as a local record of the full experiment history.

---

## Resuming

If a previous session was interrupted, the agent detects existing `results.tsv` and `autoresearch/*` branch, reads the recovery document (`autoresearch.md`), and continues the loop without re-running the baseline or asking questions.

---

## Safety

- **Scoped edits** — the agent only modifies files explicitly marked as in-scope
- **No dependency changes** — new packages and dependencies are off-limits by default
- **Evaluation integrity** — the measurement harness is read-only; the agent cannot game the metric
- **Git isolation** — all work happens on a dedicated branch; main is untouched
- **Commit-before-run** — every experiment is committed before execution, so crashes never lose the attempted change
- **Untracked logs** — `results.tsv` and `run.log` are never committed

---

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code** — generalized protocol design
- Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) — original concept and `program.md`
