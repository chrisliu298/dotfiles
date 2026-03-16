---
name: push
description: |
  Commit all changes in a single commit and push to the remote. Use when the user says
  "commit and push", "push this", "ship it", "save and push", or invokes /push. This is
  for a simple, single-commit workflow — not atomic commits. Do NOT create a pull request.
user-invocable: true
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*)
---

# Push

Commit all current changes in a single commit and push to the remote.

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged): !`git diff HEAD`
- Recent commits (for message style): !`git log --oneline -10`

## Commit message convention

Before creating the commit, study `git log --oneline -10`. Match the exact format: prefix style (if any), capitalization, punctuation, and tone. Do not invent your own convention.

## Workflow

1. **Stage changes** — add all modified and untracked files relevant to the work. Prefer `git add <paths>` over `git add -A` to avoid accidentally staging secrets or junk files. If all changes are clearly intentional, `git add -A` is fine.
2. **Commit** — write a concise message that follows the repo's convention. Focus on *what changed and why*, not listing every file. Use a HEREDOC for the message to preserve formatting.
3. **Push** — run `git push`. If no upstream is set, use `git push -u origin HEAD`.

## Constraints

- Do NOT split changes into multiple commits — this skill is for a single commit covering all changes.
- Do NOT create a pull request.
- Do NOT rebase, squash, or amend unless explicitly asked.
- If there are no changes to commit, say so and stop.
