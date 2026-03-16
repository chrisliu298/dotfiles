# /push

Commit all changes in a single commit and push to the remote. Simple single-commit workflow — use `/atomic-push` for multiple logical commits.

## Usage

```
/push
```

## How it works

1. Stages all modified and untracked files (prefers `git add <paths>` over `git add -A`)
2. Commits with a message matching the repo's existing convention (detected from `git log`)
3. Pushes (sets upstream if needed)

## Constraints

- Single commit covering all changes — does NOT split into multiple commits
- Does NOT create a pull request
- Does NOT rebase, squash, or amend
