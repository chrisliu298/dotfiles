# /push

Commit all changes in a single commit and push to the remote. Use `/atomic-push` for multiple logical commits.

## Usage

```
/push
```

## How It Works

1. Stages all modified and untracked files (prefers `git add <paths>` over `git add -A`)
2. Commits with a message matching the repo's existing convention (detected from `git log`)
3. Pushes the branch (sets upstream if needed)

## Constraints

- Single commit covering all changes — does not split into multiple commits
- Does not create a pull request
- Does not rebase, squash, or amend
