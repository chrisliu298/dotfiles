---
description: |
  Simplify and beautify code changes on the current branch. Use when the user says "beautify",
  "make it simple", "clean up the code", "simplify my branch", "make this more readable",
  "reduce complexity", or invokes "beautify". Also trigger when reviewing code that feels
  overengineered, has too many arguments, nests too deeply, or uses try-catch where asserts
  belong — even if the user doesn't say "beautify" explicitly. Do NOT use for removing AI slop
  (use deslop) or for code review without editing (use lbreview).
user-invocable: true
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Read, Edit, Grep, Glob
effort: high
---

# Beautify

Beautify the changed code on this branch so a reader can understand it by skimming, not studying.

The goal is not abstraction or "elegance." The goal is fewer states, flatter flow, and code that is harder to misuse by accident.

## Context

Determine the diff to beautify, using the first one that produces output:
1. !`git diff --cached`
2. !`git diff`
3. !`git diff main..HEAD 2>/dev/null || git diff master..HEAD`

If all are empty, say "Nothing to beautify" and stop.

Before editing, **read the full file** (not just the diff). The surrounding code is the style guide. Improve the changed code in a way that fits the existing file.

## What to optimize for

### 1. Make the code skimmable

- Use **early returns** to eliminate nesting. Guard clauses at the top, happy path at the bottom.
- Prefer **fewer lines** when the shorter version is at least as clear.
- Avoid **cleverness**. Straightforward beats compact.
- **Do not over-extract.** A function called from one place is indirection, not abstraction. Inline it.

```text
// Before
if user exists:
  if user is active:
    if user has permission:
      doWork()

// After
if user does not exist: return
if user is not active: return
if user lacks permission: return
doWork()
```

### 2. Reduce the number of possible states

- **Minimize states.** Remove or narrow any state that is not strictly necessary.
- Keep a **low argument count.** Each argument is a knob the caller can turn — remove overrides that aren't genuinely needed.
- **Required means required.** Do not make parameters optional if correct behavior depends on them.
- Use **discriminated unions** when a value can be one of several kinds, and **exhaustively handle** all variants — fail on unknown ones.

```text
// Before
saveReport(report, format = null)
  if format is null: format = "pdf"

// After
saveReport(report, format)
```

### 3. Trust invariants instead of papering over them

This is the part Claude most commonly gets wrong — the instinct is to add safety, but defensive fallbacks at internal boundaries hide real bugs and widen behavior.

- **No defensive code** for impossible states. If the types guarantee a value is present, do not check for null.
- Prefer **asserts over defaults** — a default silently hides a broken assumption.
- Prefer **asserts over try-catch** when failure means an invariant was broken, not that an error is expected and recoverable.

```text
// Before
try:
  user = db.get(id)
  return user ?? DEFAULT_USER
catch:
  return DEFAULT_USER

// After
user = db.get(id)
assert user exists, "No user for id: {id}"
return user
```

### 4. Keep the branch focused

- **No unnecessary changes.** Remove changes not strictly required for the feature.
- Improve only the changed code and the minimum nearby code needed to make it coherent.

## Gotchas

These are the real failure points when executing this skill:

- **Over-removing defensive code at system boundaries.** The "trust invariants" principle applies to *internal* code paths. Keep validation at real boundaries: user input, external API responses, file I/O. The test is: does this value come from code you control? If yes, trust types. If no, validate.
- **Simplifying code that is intentionally verbose.** Some code is complex because the problem is complex. Read the surrounding context before simplifying — if a function handles 5 edge cases, those cases probably exist for a reason.
- **Removing comments that look redundant but explain business logic.** "// Skip weekends" next to a date check looks obvious, but removing it hides the business rule. Only remove comments that literally restate the code's mechanics.
- **Narrowing types on public APIs.** Making a parameter required in internal code is a simplification. Making it required in a published API is a breaking change.
- **Scope creep into untouched code.** The diff is the scope. Nearby code that violates these principles is not your concern.

## What NOT to change

- **Code outside the diff** — even if nearby code violates these principles
- **Existing patterns in untouched code** — match the file's conventions
- **Tests** — test code has different goals
- **Public API type definitions** — breaking change, not simplification
- **Comments that explain *why***

**When in doubt, leave it in.**

## Workflow

1. Read the diff from Context above
2. Identify files with changed code
3. Read each file in full before editing
4. Apply the principles — edit in place
5. When principles compete, prefer the change that removes the most mental overhead with the least scope expansion
6. Do not `git add` your changes

When done, report a 1-3 sentence summary of what you changed.
