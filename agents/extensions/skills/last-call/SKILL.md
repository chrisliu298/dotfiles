---
name: last-call
description: |
  Session-end quality review. Deep-reads every changed file and evaluates correctness,
  documentation debt, architecture, and session completeness. Invoke with /last-call.
allowed-tools: Read, Edit, Grep, Glob, Agent, Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(git stash list:*), Bash(git rev-parse:*), Bash(git show:*)
user-invocable: true
---

# Last Call — Session-End Quality Review

Thorough close-out of the current session. Not a skim — read every changed line with production-shipping rigor.

## Principles

- **No heuristics**: Read every changed file in full context. Do not sample or skip.
- **Long-term thinking**: Evaluate as if you will maintain this code for years.
- **Flag, don't fix**: Report findings with specifics. Only apply mechanical fixes (debug artifacts, typos) without asking.

## Context

- Branch: !`git rev-parse --abbrev-ref HEAD`
- HEAD: !`git rev-parse --short HEAD`
- Status: !`git status --short`
- Staged: !`git diff --cached --stat`
- Unstaged: !`git diff --stat`
- Recent commits: !`git log --oneline -20`
- Stashed work: !`git stash list`

## Step 1: Identify Session Scope

Determine what changed this session:

1. Identify session commits using this heuristic chain:
   - If the conversation includes git commit actions, those SHAs are the session commits
   - Otherwise, use commits from the last 2 hours (`git log --since='2 hours ago'`) and flag the boundary as approximate
2. Collect uncommitted changes: `git diff` + `git diff --cached`
3. Note untracked files and stashed work
4. List every file touched across all of the above

If nothing to review (clean tree, no session commits, no stashed work), say so and stop.

## Step 2: Deep Review

For every changed file, read it in full — not just the diff hunks. Evaluate in this order:

1. **Correctness** — Bugs, logic errors, race conditions, security vulnerabilities. Incomplete implementations, TODO/FIXME/HACK markers introduced this session. Debug artifacts (leftover print/console.log, commented-out code, temporary workarounds). Test gaps for changed code paths.

2. **Documentation** — For each changed file, check related docs (README, CLAUDE.md, AGENTS.md, CHANGELOG, design docs, inline comments). Are any references now stale? Does new behavior lack documentation? Does the project's CLAUDE.md need updating?

3. **Architecture** — Pattern and convention consistency. Unearned abstractions. Broken contracts or violated assumptions. Incomplete migrations. Would a future maintainer understand why these changes were made?

4. **Session completeness** — Was the user's original goal fully addressed? Any scope creep? Uncommitted work that should be staged or gitignored? Contradictory or orphaned modifications?

Rate each finding: **critical** / **warning** / **nit**. Cite file paths and line numbers.

For large change sets (10+ files), consider running review lenses as parallel subagents for depth.

## Step 3: Act & Report

### Mechanical fixes (apply without asking)

- Remove unambiguous debug artifacts from files changed this session
- Fix obvious typos in files changed this session

Do **not** modify code logic or documentation without user confirmation.

### Documentation proposals (include in report, do not apply)

- Draft content for stale or missing documentation
- Draft CHANGELOG entry if the project maintains one

### Output

```
## Session Review

### Accomplished
- [What was done this session]

### Fixes Applied
- [Debug artifacts removed, typos fixed — with file:line]

### Needs Attention
- [Findings requiring action — severity, file:line, recommendation]

### Documentation Proposals
- [Draft updates for stale/missing docs — show the proposed content]

### Loose Ends
- [Uncommitted work, stashed changes, TODOs, incomplete migrations]
```

Omit any section with no items. No filler.

If the session produced significant work, close with:
"Consider running `/handover` to create continuity notes for the next session."
