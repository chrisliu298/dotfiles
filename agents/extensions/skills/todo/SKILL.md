---
effort: low
description: |
  Maintain a single TODO.md at the project root so task state survives session
  boundaries, compaction, and multi-day gaps. Use only for work large or complex
  enough that the native in-session checklist can't track it well — multi-day
  refactors, migrations, or anything spanning several sessions. Also trigger on
  "/todo", "track this", "checkpoint", or "save for next time". Do NOT trigger on
  small one-shot tasks (a single bug fix, rename, or one-liner), work the native
  checklist handles fine, in-session-only todo tracking, or when there's no clear
  project root.
user-invocable: true
---

# Todo

Maintain a single `TODO.md` at the project root so task state survives session boundaries, compaction events, and multi-day gaps. Multiple tracking docs fail because something always gets missed; one file means nothing falls through.

The native in-session task list (`TaskCreate` / `TodoWrite`) covers within-session granularity — steps within an item, decisions made right now. `TODO.md` is the durable layer above it: high-level items that need to outlast the current context window. The two are complementary, not competing.

## When to use

This skill is a step up from the native in-session checklist (`TaskCreate` / `TodoWrite`), not a replacement for it. Default to the native checklist. Only reach for `TODO.md` when the task is large or complex enough that the native list can't hold it well — too many moving parts to keep straight in one window, or state that must outlast the session. If the native checklist tracks the whole task comfortably, stay there.

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

The frontmatter is the orientation block: `task` is the one-line goal, `started_at` is when work began, `last_session` is the most recent session date in `YYYY-MM-DD`. Update `last_session` whenever you flush state to the file — or run `docmaint stamp --attest flush` (see The discipline), which sets it to today and re-renders the Overview in one step.

Items are markdown checkboxes, one line each. Inline blockers as `— blocked on …` rather than nested bullets — the file should stay scannable when it grows long. New work uncovered during a session goes to `## To Do`.

### Overview block (auto-derived)

Directly after the frontmatter, `TODO.md` may carry an auto-derived **Overview** — a fixed-size, human-facing snapshot of the checklist, fenced by HTML-comment markers:

```markdown
<!-- TODO-OVERVIEW:BEGIN input_sha=8f31c7e0d2b4 rendered_at=2026-05-07T18:42-07:00 -->
## Overview
**Progress:** 6/14 done (43%) `[####------]` · 3 in progress · 5 to do
**Areas:** Backend 4/6 (67%) · SDK 1/5 (20%) · Infra 1/3 (33%) · Other 0/0
**Needs attention:** 2 — Backend: callback handler blocked on infra #4821; SDK: waiting on human deprecation-window choice
**Recent:** latest 2026-05-02 Provision IdP app · started 2026-05-01 · last touched 2026-05-07 · 6-day span
<!-- TODO-OVERVIEW:END -->
```

It is **derived, not authored** — a projection of the checkboxes below, never a second source of truth. Don't hand-edit anything between the markers; fix the checklist and re-render (see The discipline). The render script owns only the marked region — everything below `:END` is your hand-maintained checklist, echoed back untouched.

**Area tags.** Items may carry one optional trailing `#area/<slug>` tag for the per-area tally:

```markdown
- [ ] Wire up callback handler — blocked on infra ticket #4821 #area/backend
- [x] 2026-05-02 — Provision IdP app #area/infra
```

The slug renders title-cased, so write it uppercase (`#area/SDK`) to keep it uppercase. Tags are optional and append-only — one token, no extra line; untagged items still count toward totals under **Other**. Use `#area/` (not a bare `#backend`) so it can't be confused with issue refs like `#4821`. Keep areas few and broad — they're an at-a-glance grouping, not a subsystem taxonomy.

## The discipline

### Bootstrap (session start)

Before doing any other work, read `./TODO.md`. If it exists:

1. Note the `task` and `last_session` — orient on what this is and when it was last touched
2. Reconcile the In Progress item against the actual state of the code. If Done claims something shipped but the codebase shows otherwise, surface the drift to the user before proceeding — don't silently re-execute work, and don't assume the file is wrong
3. Confirm briefly with the user what to pick up first

If your harness can run shell commands, use the `docmaint` helper (`<this-skill-dir>/scripts/docmaint`) — a stdlib-only script that `todo`, `exec-status`, and `mental-seal` all share with the **same verbs**: `locate · scaffold · check · sync · stamp · print · self-test` (exit `0` ok · `1` stale/missing · `2` malformed). It auto-locates `TODO.md` by searching upward to the project/git root, so you can call it from any subdirectory. On bootstrap run `docmaint check`; if it reports the Overview stale or missing (e.g. the checklist was hand-edited), run `docmaint sync` before trusting the numbers. If you can't run the script, keep the checklist correct and treat the Overview as possibly stale.

If it doesn't exist and the work qualifies as long-running, create it. Seed `## In Progress` with the immediate next step and `## To Do` with the rest of what the user described.

### Work (during the session)

When starting a To Do item, move it to In Progress. When understanding shifts or a blocker appears, append a one-line note to the In Progress item. When you uncover new work, add it to To Do. Flush updates regularly rather than batching them to the end of the session — sudden compaction or an unexpected interruption shouldn't lose state.

After each flush, re-render the Overview: `<this-skill-dir>/scripts/docmaint sync`. It's mechanical and idempotent — it rewrites only the Overview block from the current checkboxes, and does nothing when they haven't changed. Never hand-edit the Overview to make it read better; fix the checkbox line instead.

### Close (session end or compaction warning)

Before stopping, when the user signals they're wrapping up, or when context starts filling up:

1. Move completed items from In Progress to Done with a `YYYY-MM-DD —` prefix
2. Flush the session: `<this-skill-dir>/scripts/docmaint stamp --attest flush` — sets `last_session` to today and re-renders the Overview in one step (or update `last_session` by hand, then `docmaint sync`)
3. Run the gate: `<this-skill-dir>/scripts/docmaint check --handoff` — exits non-zero if the Overview is stale, so a broken handoff is loud rather than silent

Don't wait for the user to ask. The file is only useful if it's current when the session ends.

## Why this design

- **Single file** avoids the "I forgot to check the other doc" failure that plagued multi-file approaches. One canonical place means nothing slips through.
- **Markdown checkboxes** read equally well to the model parsing the file and to a human scanning it directly. No format surprises.
- **Date-stamped Done** acts as a long-form audit trail — when work spans weeks, it's useful to see what shipped when, and to bisect when something regressed.
- **Frontmatter dates** let the model see at a glance whether this is a two-day or two-month effort, which informs how aggressively to rely on the file as ground truth.
- **The Overview is derived, not authored.** A script projects progress, per-area tallies, blockers, and time-sense from the same checkboxes, so a human gets the global picture at the top of the file while the numbers can't drift from reality — and the one-line-per-item authoring discipline is untouched (the block is generated, never hand-written).
- **Area tags are optional, single-line metadata.** `#area/<slug>` adds grouping without sub-headings, a frontmatter registry, or multi-line items; untagged items stay valid and roll into Other.
- **The script is an accelerator, not the mechanism.** The Overview's format is documented above, so an agent whose harness can't run the script can hand-render it or skip it — the skill stays portable across Claude, Codex, and Grok. Run `<this-skill-dir>/scripts/docmaint self-test` to verify the renderer. `docmaint` is one shared interface across `todo`/`exec-status`/`mental-seal`: the copies are byte-identical except a `DOC` constant, and `dotfiles.sh lint` guards against drift.

## Gotchas

- **Don't redo Done items.** If the file says something shipped, trust it unless code clearly disagrees. When state and file conflict, surface the drift to the user — don't pick a side silently.
- **Don't bloat.** One line per item. Long context belongs in linked tickets, commit messages, or a separate design doc, not in TODO.md, which needs to stay scannable as it grows.
- **Don't auto-create on small tasks.** The description leans pushy because under-triggering is the bigger risk, but a single bug fix doesn't need a TODO.md. If the work fits comfortably in one session and won't be revisited, skip the file.
- **Don't shadow the native task list.** In-session steps belong in `TaskCreate` / `TodoWrite`. `TODO.md` is for items that need to outlast the conversation. Using both at the right altitude is the goal, not picking one.
- **Don't place it outside the project root.** If `pwd` is `$HOME`, a tmp dir, or a directory with no recognizable project boundary, ask the user where the file should live before creating anything.
- **Don't hand-edit the Overview block.** Everything between the `TODO-OVERVIEW` markers is regenerated from the checkboxes; edits there are overwritten. Fix the checkbox, date, blocker note, or area tag, then re-render.
- **Don't over-tag.** Areas are a few broad themes for an at-a-glance scan — if every item needs its own area, the tally stops helping. And use `#area/<slug>`, never a bare `#tag` (it collides with issue refs like `#4821`).
- **Don't let the Overview become a second `STATUS.md`.** It stays todo-internal — counts, areas, blockers, recency. Plain-English stakeholder interpretation belongs in `exec-status`/`STATUS.md`.
- **Re-render after edits; re-check on resume.** If `docmaint check` flags the block stale (e.g. someone hand-edited the checklist), run `docmaint sync` before relying on the numbers.
