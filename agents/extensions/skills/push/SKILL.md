---
name: push
description: |
  Commit all changes in a single commit and push to the remote. This is the default
  skill for "commit and push", "push this", "ship it", "save and push", or /push.
  For multiple atomic commits per logical change, use /atomic-push instead.
  Do NOT create a pull request.
user-invocable: true
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git branch:*)
---

# Push

Commit all current changes in a single commit and push to the remote.

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged): !`git diff HEAD 2>/dev/null || git diff --cached`
- Recent commits (for message style): !`git log --oneline -10`

## Commit message convention

Match the repo's existing commit style exactly — study `git log --oneline -10` from Context for prefix style, capitalization, punctuation, and tone.

## Workflow

1. **Stage changes** — review the diff for secrets, credentials, or junk files (.env, *.log, node_modules, etc.). If any are present, stage only the safe files with `git add <paths>`. Otherwise, `git add -A` is fine.
2. **Commit** — write a concise message that follows the repo's convention. Focus on *what changed and why*, not listing every file. Use a HEREDOC for the message to preserve formatting.
3. **Push** — run `git push`. If no upstream is set, use `git push -u origin HEAD`.

## Constraints

- Do NOT split changes into multiple commits — this skill is for a single commit covering all changes.
- Do NOT create a pull request.
- Do NOT rebase, squash, or amend unless explicitly asked.
- If `git push` is rejected (e.g., non-fast-forward), report the error and stop. Do NOT force-push.
- If there are no changes to commit, say so and stop.
