---
name: deslop
description: |
  Remove AI-generated slop from code changes. Checks the diff against main and cleans up
  unnecessary comments, defensive checks, single-use variables, redundant casts, and style
  inconsistencies introduced by AI. Use when the diff looks bloated after a coding task,
  or when user says "clean up", "remove slop", "deslop", "simplify the diff", or invokes
  /deslop. Do NOT use for deliberate refactoring or feature changes.
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Read, Edit, Grep, Glob
---

## Context

Determine the diff to review, using the first one that produces output:
1. !`git diff --cached`
2. !`git diff`
3. !`git diff main..HEAD` or !`git diff master..HEAD`

## Your task

Check the diff against main, and remove all AI-generated slop introduced in this branch.

Before editing, **read the full file** (not just the diff) to understand the existing style — comment density, docstring usage, error handling patterns, naming conventions. The existing code is the style guide.

### What to remove

- **Comments that restate the code.** Remove `// Check if value is null` before `if (val === null)`. Keep comments that explain *why* — business rules, non-obvious edge cases, workarounds. Test: could a competent developer figure this out from the code alone? If yes, it's slop.
- **Docstrings/JSDoc added to a file that doesn't use them.** If the existing code has no docstrings, new code shouldn't either — even on new methods. Match the file's convention.
- **Single-use variables** declared and used once on the next line — inline them. Exception: keep when the expression is genuinely complex (3+ chained operations) and the name adds real clarity.
- **Defensive checks at internal boundaries.** AI adds null checks, type guards, and try/catch to every function. For internal code called by trusted codepaths, strip them. Keep defensive code only at real system boundaries (user input, external API responses, untrusted file I/O).
- **Redundant type annotations and casts.** `as Foo` when already inferred, explicit `: string` on a string variable, etc. Remove unless the file consistently uses explicit annotations.
- **Style inconsistencies.** If the file uses `let`, don't switch to `const`. If it doesn't use JSDoc, remove JSDoc. Match existing patterns.
- **Dead code.** Attributes set but never read, variables assigned but unused.
- Consistency of the changes with AGENTS.md or CLAUDE.md requirements.

### What to keep

- **The actual feature** — new functions, new logic, new imports required by new code.
- **Comments that explain *why*, not *what*** — business logic, edge case rationale, "this works around bug X".
- **Security-rationale comments** — comments explaining WHY a specific security measure is used (timing-safe comparison, CSRF protection, sanitization, constant-time operations). Security reasoning should be explicit even if familiar to experts, because removing the comment risks someone later "simplifying" the code and introducing a vulnerability.
- **Defensive code at real system boundaries** — input validation at API endpoints, checks on user-provided data, error handling for external services.
- **Helper functions used more than once** — if a function is called from multiple places, it's a real abstraction, not slop. Only inline single-call helpers.

**When in doubt, leave it in.** Under-removal is safer than over-removal.

Do not `git add` your changes. Do not unstage (`restore --staged`) any staged changes.

When done, report a 1-3 sentence summary of what you changed.
