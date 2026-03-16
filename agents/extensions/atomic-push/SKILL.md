---
name: atomic-push
description: |
  Commit and push changes to remote with separate atomic commits for each logical change
  (one commit per feature/fix). Use when asked to "commit and push" or "atomic commits".
  Do NOT create a pull request. Invoke with /atomic-push.
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*)
---

# Atomic Push

Turn the current working tree into a clean branch with small, well-scoped commits, then push.

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged): !`git diff HEAD`
- Recent commits (for message style): !`git log --oneline -10`

## Inspect commit message convention

Before creating any commits, study the output of `git log --oneline -10`. Identify the exact format: prefix style (e.g., `feat:`, `fix:`, imperative verb, etc.), capitalization, punctuation, and tone. All commit messages you create MUST strictly follow this convention — do not invent your own style.

## Create atomic commits

1. Group all changes into logical units (feature/fix/refactor/docs/etc.).
2. For each unit:
   - Stage only relevant hunks/files (`git add -p`, `git add <paths>`).
   - Sanity-check the staged diff (`git diff --cached`).
   - Commit with a concise message strictly matching the repo's convention identified above.
3. Repeat until `git status` is clean (or only intentionally-uncommitted files remain).

## Push

- Push the current branch (`git push`).
- If the branch has no upstream, set it (`git push -u origin HEAD`).

## Constraints

- Do NOT create a pull request.
- Do NOT rebase/squash/amend unless explicitly asked.
- If changes cannot be cleanly separated, explain why and prefer fewer commits over tangled ones.
