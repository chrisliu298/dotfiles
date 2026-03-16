---
name: sync-upstream
description: |
  Sync a forked repository with its upstream remote. Use when the user says
  "sync upstream", "update from upstream", "pull upstream", "sync fork",
  "sync repo with upstream", or invokes /sync-upstream. Handles adding the
  upstream remote, fetching, rebasing, and optionally force-pushing to origin.
user-invocable: true
allowed-tools: Bash(git remote:*), Bash(git fetch:*), Bash(git stash:*), Bash(git rebase:*), Bash(git log:*), Bash(git status:*), Bash(git push:*)
---

# Sync Upstream

Sync a forked repository's current branch with the upstream remote.

## Context

- Current remotes: !`git remote -v`
- Current branch: !`git branch --show-current`
- Working tree status: !`git status --short`

## Workflow

1. **Check for upstream remote** — run `git remote -v`. If no `upstream` remote exists, infer it from the `origin` URL (same host, same repo name, different org) and ask the user to confirm before adding. If the upstream repo is ambiguous, ask the user for the URL.

2. **Fetch upstream** — run `git fetch upstream`.

3. **Check divergence** — run `git log --oneline HEAD..upstream/<branch>` (where `<branch>` matches the current branch) to show the user how many new commits are incoming.

4. **Handle local changes** — if `git status` shows uncommitted changes, `git stash` before rebasing and `git stash pop` after.

5. **Rebase** — run `git rebase upstream/<branch>`. If conflicts arise, stop and tell the user rather than resolving automatically.

6. **Report result** — show a brief summary: how many commits were pulled in and whether local changes were preserved.

7. **Offer to push** — ask the user if they want to force-push to `origin` to update their fork. Only push after explicit confirmation. Use `git push --force-with-lease` (not `--force`) for safety.

## Constraints

- Do NOT force-push without the user's confirmation.
- Do NOT resolve rebase conflicts automatically — surface them and let the user decide.
- Do NOT modify branches other than the current one.
- Default to `main` as the upstream branch if the current branch name doesn't exist on upstream.
