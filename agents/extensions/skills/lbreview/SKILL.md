---
name: lbreview
user-invocable: true
description: |
  Careful and thorough code review of changes against main. Analyzes the diff to understand
  the goal, evaluates benefits, identifies pitfalls, and suggests simplifications. Use when
  user asks for code review, says "review my changes", "check the diff", "what do you think
  of these changes", or invokes "lbreview". Do NOT use for session-end review; use last-call
  instead.
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Read, Grep, Glob
effort: high
---

## Context

Determine the diff to review, using the first one that produces output:
1. !`git diff --cached` (staged changes)
2. !`git diff` (unstaged changes)
3. !`git diff HEAD` (all uncommitted changes — staged + unstaged combined)

If all are empty, say "Nothing to review" and stop.

## Your task

Check the diff against main, and review this change carefully.

Careful review means, in this order:

1. **Understand the change** — What is this change about? State the author's intent explicitly — the adversarial lenses in step 8 challenge whether the work achieves this intent well.
2. **Evaluate the benefits** — How does the change achieve this goal? What are the clear benefits and improvements?
3. **Identify pitfalls** — What are the potential issues or pitfalls with this change? (Don't bother about backwards-compatibility.)
4. **Check for gaps** — Is there something obvious that the change might be missing?
5. **Suggest improvements** — What are potential improvements we could make to this change?
6. **High-level simplifications** — Could we simplify the high-level design?
7. **Implementation simplifications** — Could we simplify the implementation?

Present your review in this structured order. Be direct and specific — reference file names and line numbers.

8. **Adversarial lenses** — Read `references/lenses.md`, then apply lenses based on diff size. Count the total number of lines in the `git diff` output (including context lines, `@@` headers, and `+`/`-` lines — everything `git diff` prints):
   - Small (< 50 lines): Skeptic only
   - Medium (50–200 lines): Skeptic + Architect
   - Large (200+ lines): Skeptic + Architect + Minimalist

   For each lens, adopt an adversarial posture: your job is to find real problems, not validate the work. For each finding, cite file:line and rate severity: **high** (blocks ship), **medium** (should fix), **low** (worth noting). Skip a lens if it produces no findings.

9. **Verdict** — Based on lens findings, give one of:
   - **PASS** — no high-severity findings
   - **CONTESTED** — high-severity findings but lenses disagree
   - **REJECT** — high-severity findings with consensus

   Then apply your own judgment: which findings warrant action and which are false positives or stylistic overreach? State accept/reject for each high or medium finding with a one-line rationale.
