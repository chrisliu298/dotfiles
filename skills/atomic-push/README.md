# /atomic-push

Commit and push changes to remote with separate atomic commits for each logical change (one commit per feature/fix).

## Usage

```
/atomic-push
```

Groups all working tree changes into logical units, stages each independently, commits with a message matching the repo's existing convention, then pushes.

## How it works

1. Inspects `git log --oneline -10` to detect commit message convention
2. Groups changes into logical units (feature/fix/refactor/docs)
3. For each unit: stages relevant hunks/files, sanity-checks the staged diff, commits
4. Pushes the branch (sets upstream if needed)

## Constraints

- Does NOT create a pull request
- Does NOT rebase, squash, or amend
- If changes can't be cleanly separated, prefers fewer commits over tangled ones
