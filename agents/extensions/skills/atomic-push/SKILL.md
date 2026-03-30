---
name: atomic-push
description: |
  Commit and push changes to remote as separate logical commits (one commit per
  feature/fix/refactor). Use when the user explicitly wants "atomic commits",
  "separate commits", "split into commits", "one commit per change", or invokes
  "atomic-push". For simple single-commit pushes, use push instead.
  Do NOT create a pull request.
user-invocable: true
effort: medium
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git branch:*)
---

# Atomic Push

Turn the current working tree's changes into small, well-scoped commits on the current branch, then push.

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged): !`git diff HEAD 2>/dev/null || git diff --cached`
- Recent commits (for message style): !`git log --oneline -10`

## Commit message convention

Match the repo's existing commit style exactly — study `git log --oneline -10` from Context for prefix style (e.g., `feat:`, `fix:`, imperative verb), capitalization, punctuation, and tone. Do not invent your own convention.

## Create atomic commits

1. Group all changes into logical units (feature/fix/refactor/docs/etc.).
2. For each unit:
   - Stage only the relevant files (`git add <paths>`). Do NOT use `git add -p` — it requires interactive input.
   - Sanity-check the staged diff (`git diff --cached`).
   - Commit with a concise message strictly matching the repo's convention.
3. Repeat until all changes intended for this push are committed. If any files are intentionally left uncommitted, tell the user before pushing.

## Push

- Push the current branch (`git push`).
- If the branch has no upstream, set it (`git push -u origin HEAD`).

## Constraints

- If there are no changes to commit, say so and stop.
- Do NOT create a pull request.
- Do NOT rebase/squash/amend unless explicitly asked.
- If `git push` is rejected (e.g., non-fast-forward), report the error and stop. Do NOT force-push.
- If changes cannot be cleanly separated, explain why and prefer fewer commits over tangled ones.
