---
description: |
  Maintain a single TODO.md at the project root so task state survives session
  boundaries, compaction events, and multi-day gaps. Use this skill whenever a
  task is large or long-running — multi-day refactors, migrations, anything
  the user describes as "this will take a while", "across several sessions",
  or "we'll pick this up tomorrow", projects spanning multiple days, or work
  where context will need to survive compaction. Also trigger when the user
  invokes "/todo" explicitly, or asks to "track this", "checkpoint", or "save
  what we're doing for next time". The cost of starting a TODO.md is small;
  the cost of not having one when work spans sessions is hours of
  re-explanation. Do NOT trigger on small one-shot tasks (a single bug fix,
  rename, or one-line change), on in-session-only todo tracking (the native
  task list handles that), or when the working directory has no clear project
  root.
user-invocable: true
---

# Todo

Maintain a single `TODO.md` at the project root so task state survives session boundaries, compaction events, and multi-day gaps. Multiple tracking docs fail because something always gets missed; one file means nothing falls through.

The native in-session task list (`TaskCreate` / `TodoWrite`) covers within-session granularity — steps within an item, decisions made right now. `TODO.md` is the durable layer above it: high-level items that need to outlast the current context window. The two are complementary, not competing.

## When to use

Reach for this skill when:

- Work spans multiple sessions or days
- The user says "this will take a while", "across several sessions", "we'll pick this up tomorrow"
- The session has accumulated enough state that compaction would lose meaningful context
- The user invokes `/todo` directly, or asks to "track this", "checkpoint", or "save state"

Skip it when:

- The task is one-shot — a single bug fix, rename, doc edit, small refactor
- Tracking is in-session only (use the native task list)
- The working directory is `$HOME` or has no clear project root — ask the user where to put the file rather than guessing

## File format

Project root, named `TODO.md`. YAML frontmatter, then three sections:

```markdown
---
task: Migrate auth to OIDC
started_at: 2026-05-01
last_session: 2026-05-03
---

## In Progress
- [ ] Wire up callback handler — blocked on infra ticket #4821

## To Do
- [ ] Update SDK consumers
- [ ] Run staging soak

## Done
- [x] 2026-05-01 — Spike OIDC vs SAML, picked OIDC
- [x] 2026-05-02 — Provision IdP app
```

The frontmatter is the orientation block: `task` is the one-line goal, `started_at` is when work began, `last_session` is the most recent session date in `YYYY-MM-DD`. Update `last_session` whenever you flush state to the file.

Items are markdown checkboxes, one line each. Inline blockers as `— blocked on …` rather than nested bullets — the file should stay scannable when it grows long. New work uncovered during a session goes to `## To Do`.

## The discipline

### Bootstrap (session start)

Before doing any other work, read `./TODO.md`. If it exists:

1. Note the `task` and `last_session` — orient on what this is and when it was last touched
2. Reconcile the In Progress item against the actual state of the code. If Done claims something shipped but the codebase shows otherwise, surface the drift to the user before proceeding — don't silently re-execute work, and don't assume the file is wrong
3. Confirm briefly with the user what to pick up first

If it doesn't exist and the work qualifies as long-running, create it. Seed `## In Progress` with the immediate next step and `## To Do` with the rest of what the user described.

### Work (during the session)

When starting a To Do item, move it to In Progress. When understanding shifts or a blocker appears, append a one-line note to the In Progress item. When you uncover new work, add it to To Do. Flush updates regularly rather than batching them to the end of the session — sudden compaction or an unexpected interruption shouldn't lose state.

### Close (session end or compaction warning)

Before stopping, when the user signals they're wrapping up, or when context starts filling up:

1. Move completed items from In Progress to Done with a `YYYY-MM-DD —` prefix
2. Update `last_session` in the frontmatter
3. Write the file

Don't wait for the user to ask. The file is only useful if it's current when the session ends.

## Why this design

- **Single file** avoids the "I forgot to check the other doc" failure that plagued multi-file approaches. One canonical place means nothing slips through.
- **Markdown checkboxes** read equally well to the model parsing the file and to a human scanning it directly. No format surprises.
- **Date-stamped Done** acts as a long-form audit trail — when work spans weeks, it's useful to see what shipped when, and to bisect when something regressed.
- **Frontmatter dates** let the model see at a glance whether this is a two-day or two-month effort, which informs how aggressively to rely on the file as ground truth.

## Gotchas

- **Don't redo Done items.** If the file says something shipped, trust it unless code clearly disagrees. When state and file conflict, surface the drift to the user — don't pick a side silently.
- **Don't bloat.** One line per item. Long context belongs in linked tickets, commit messages, or a separate design doc, not in TODO.md, which needs to stay scannable as it grows.
- **Don't auto-create on small tasks.** The description leans pushy because under-triggering is the bigger risk, but a single bug fix doesn't need a TODO.md. If the work fits comfortably in one session and won't be revisited, skip the file.
- **Don't shadow the native task list.** In-session steps belong in `TaskCreate` / `TodoWrite`. `TODO.md` is for items that need to outlast the conversation. Using both at the right altitude is the goal, not picking one.
- **Don't place it outside the project root.** If `pwd` is `$HOME`, a tmp dir, or a directory with no recognizable project boundary, ask the user where the file should live before creating anything.
