---
name: sync-upstream
description: |
  Sync a forked repository with its upstream remote. Use when the user says
  "sync upstream", "update from upstream", "sync fork", "rebase on upstream",
  "sync repo with upstream", or invokes "sync-upstream". Only applies to repos
  that are forks. Do NOT use for simple git pull on non-forked repos.
user-invocable: true
effort: medium
allowed-tools: Bash(git remote:*), Bash(git fetch:*), Bash(git stash:*), Bash(git rebase:*), Bash(git log:*), Bash(git status:*), Bash(git push:*), Bash(git branch:*), Bash(gh repo:*)
---

# Sync Upstream

Sync a forked repository's current branch with the upstream remote.

## Context

- Current remotes: !`git remote -v`
- Current branch: !`git branch --show-current`
- Working tree status: !`git status --short`
- Upstream branches (if upstream exists): !`git branch -r --list 'upstream/*' 2>/dev/null | head -10`

## Workflow

1. **Check for upstream remote** — use the remotes from Context. If no `upstream` remote exists, try `gh repo view --json parent -q '.parent.owner.login + "/" + .parent.name'` to find the parent repo. If that fails or the repo is not a GitHub fork, ask the user for the upstream URL. Confirm with the user before running `git remote add upstream <url>`.

2. **Fetch upstream** — run `git fetch upstream`. If this fails (network error, auth issue, deleted repo), report the error and stop.

3. **Determine upstream branch** — check if `upstream/<current-branch>` exists (`git branch -r --list 'upstream/<current-branch>'`). If it does not, tell the user and ask which upstream branch to rebase onto (suggest `main` as a likely default). Do not silently fall back.

4. **Check divergence** — run `git log --oneline HEAD..upstream/<branch>` to show the user how many new commits are incoming. If zero, tell the user the branch is already up to date and stop.

5. **Handle local changes** — if `git status --porcelain` produces output, run `git stash push -m "sync-upstream"` before rebasing. Track whether a stash was created so you only pop if you actually stashed.

6. **Rebase** — run `git rebase upstream/<branch>`. If conflicts arise, stop and tell the user rather than resolving automatically.

7. **Restore stashed changes** — if a stash was created in step 5, run `git stash pop`. If this causes conflicts, inform the user that their local changes conflict with the rebased code and leave the stash intact.

8. **Report result** — show a brief summary: how many commits were pulled in and whether local changes were preserved.

9. **Offer to push** — ask whether to update `origin` with `git push --force-with-lease`. Only push after explicit confirmation.

## Constraints

- Do NOT force-push without the user's confirmation.
- Do NOT resolve rebase conflicts automatically — surface them and let the user decide.
- Do NOT modify branches other than the current one.
- Before starting, check for an in-progress rebase (`git status` will mention "rebase in progress"). If found, inform the user and ask whether to abort it or let them resolve it manually.
- If the current branch doesn't exist on upstream, ask the user which branch to sync against — do not silently fall back.
