---
effort: medium
name: push
description: |
  Commit and push the requested changes when the user asks to push, ship, or save
  and push. Does not create a pull request.
user-invocable: true
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git branch:*)
---

# Push

Commit the changes within the user’s requested scope and push them to the remote. Preserve unrelated staged and unstaged work; inspect the index as well as the working tree before committing.

## Mode selection

Inspect status + diff and pick the mode yourself — do not ask the user:

- Use **atomic** when the diff spans clearly distinct units: multiple unrelated files/areas, a mix of categories (feature + fix + docs + refactor), or > ~5 files that don't share a single theme.
- Use **single commit** for one focused change: a single file, a single feature/fix/refactor, or trivial edits (typos, formatting, version bumps, lockfile-only).
- When borderline, prefer single commit — atomic only when separation is genuinely useful.

State the chosen mode in one short line before staging (e.g., "Atomic — 3 commits: feature X, fix Y, docs Z") so the user can correct it.

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged): !`git diff HEAD 2>/dev/null || git diff --cached`
- Recent commits (for message style): !`git log --oneline -10`

## Commit message convention

Match the repo's existing commit style exactly — study `git log --oneline -10` from Context for prefix style (e.g., `feat:`, `fix:`, imperative verb), capitalization, punctuation, and tone. Do not invent your own convention.

## Workflow — single commit (default)

1. **Stage changes** — review the scoped diff for secrets, credentials, or junk files (.env, *.log, node_modules, etc.). Stage only explicitly scoped paths with `git add <paths>`, then inspect `git diff --cached` to confirm the commit contains only intended changes. If unrelated changes share a file or are already staged, isolate the intended change without discarding the user’s work; ask only if ownership or scope is unclear.
2. **Commit** — write a concise message that follows the repo's convention. Focus on *what changed and why*, not listing every file. Use a HEREDOC for the message to preserve formatting.
3. **Push** — run `git push`. If no upstream is set, use `git push -u origin HEAD`.

## Workflow — atomic

1. **Group** the requested changes into logical units (feature/fix/refactor/docs/etc.).
2. For each unit:
   - Stage only the relevant files (`git add <paths>`). Do NOT use `git add -p` — it requires interactive input.
   - Sanity-check the staged diff (`git diff --cached`).
   - Commit with a concise message strictly matching the repo's convention.
3. Repeat until all changes intended for this push are committed. If any files are intentionally left uncommitted, tell the user before pushing.
4. **Push** the current branch (`git push`). If no upstream is set, use `git push -u origin HEAD`.

## Constraints

- If there are no changes to commit, say so and stop.
- Do NOT create a pull request.
- Do NOT rebase, squash, or amend unless explicitly asked.
- If `git push` is rejected (e.g., non-fast-forward), report the error and stop. Do NOT force-push.
- In atomic mode, if changes cannot be cleanly separated, explain why and prefer fewer commits over tangled ones.
