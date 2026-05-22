# /push

Commit changes and push to the remote. The agent inspects the diff and picks single-commit or atomic mode automatically — no user toggle.

## Usage

```
/push
```

## How It Works

1. Inspects `git status` + diff and decides mode: atomic when changes span unrelated units (mixed categories, multiple distinct areas), single commit for one focused change.
2. Announces the chosen mode (and the planned commit split, in atomic) before staging so the user can correct it.
3. Stages files (prefers explicit paths over `git add -A` when secrets or junk may be present).
4. Commits with a message matching the repo's existing convention (detected from `git log --oneline -10`). Atomic mode commits each logical unit separately.
5. Pushes the branch, setting upstream if needed.

## Constraints

- Does not create a pull request.
- Does not rebase, squash, or amend.
- Never force-pushes; if `git push` is rejected, reports and stops.
- Atomic mode prefers fewer commits over tangled ones when changes can't be cleanly separated.
