---
name: exec-status
description: >-
  Maintain one plain-English STATUS.md at the working-directory root — a living executive briefing
  a non-technical stakeholder grasps in ~30 seconds: what the run is trying to do, how it's going,
  what it's found, and whether to worry (no jargon, no logs). Use for work the user kicks off and
  walks away from, or that spans many steps or sessions unwatched: autonomous research/experiment
  runs, hyperparameter sweeps, long migrations, overnight or multi-day jobs, "go run this and keep
  me posted" — and on resume in a directory that already holds a STATUS.md for an active run. Also
  trigger on explicit asks: "status report", "executive summary", "CEO update", "I keep losing
  track of progress", or "exec-status" by name. Do NOT use for in-session work you're watching,
  single edits or bug fixes, quick Q&A, or work with no durable working directory.
  Zero-context-readable — complements todo (operator checklist), autoresearch (experiment state),
  and digest (reply reformat); does not replace them.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# exec-status

Keep one file — `STATUS.md` at the run's working-directory root — that a **CEO with zero context**
can open mid-run and, in ~30 seconds, answer: *What is this trying to do? Is it going well or badly?
What has it actually found? What's next? Should I be worried?* The reader doesn't read code, logs, or
this conversation — the report is their only window, so its job is not to summarize your work but to
**translate the state of the run into plain outcomes a smart outsider can trust.**

## Bootstrap — do this before substantial work

On the **start or resume** of any qualifying run (see the description), before you dig in:

1. Look for `STATUS.md` at the working-directory root.
2. If it exists, **read it first** and reconcile it against the *actual* durable state (the files/commands
   its `For the AI` section names), then refresh it before continuing. After a context reset the report
   is the only memory that survived — trust it only after you've checked it against reality.
3. If a qualifying run is already underway and no `STATUS.md` exists, create one now. The trigger isn't
   only at t=0.

This bootstrap is the compaction defense at work: the file survives the reset on disk, and re-reading it re-engages
the discipline — but only once the file is actually reopened (see *Surviving a long run*).

## The file

One `STATUS.md` at the **working-directory root** (the project you're working in), **rewritten in place** —
never an append-only log. It is a *derived* view of durable state (results files, commits, run logs, your
notes), never the source of truth — so it's always safe to regenerate from reality and it never feeds back
into the work. Commit it or leave it untracked, your call; either way treat it as a projection you can
overwrite at any time. If the working dir is `$HOME` or has no project boundary, this skill doesn't apply —
there's no durable run to brief on. If an existing `STATUS.md` looks hand-edited or corrupted, treat it as
stale and re-derive every section from durable state.

Scaffold a new `STATUS.md` with the helper script below (or copy the template from this skill's
`assets/STATUS.template.md`). A report a CEO can trust earns that trust three ways, and the template is built around them:

- **Visible freshness.** The top line carries `Health` + `Fresh as of`, and a `How current is this` block
  states `Last checked against:` (the durable evidence the report reflects) and `Out of date if:` (the
  concrete condition that means something newer happened). A skill can't run on a timer, so "always current"
  is impossible to guarantee — but the file can at least tell the reader *exactly when to stop trusting it.*
- **Evidence-tethered claims.** Every finding names a handle a skeptic could check and a confidence label,
  so "going well" can't be asserted without backing.
- **An alarm it's allowed to sound.** A standing "Should you be worried?" line that can say *yes*. An
  all-clear is only believable from a report structurally able to raise a red flag.

## Keeping it current

There's no background timer — a skill is instructions that run while you work. So tie updates to **events you
can't miss because they're already part of the work**, not to a clock. Refresh `STATUS.md` when the **stakeholder
answer would change**: a finding lands / is reproduced /
is overturned; a phase or experiment completes; a blocker appears or clears; the Health verdict would change;
**before** a long-running command (say what's running and what result will update the report) and **after** it
finishes. Skip routine commands that change no stakeholder answer — narrating busywork is the failure, not the goal.

- **The freshness trio travels together.** Whenever you update content, also update `Fresh as of`,
  `Last checked against`, and `Out of date if`. Never bump the timestamp without re-checking the evidence
  boundary — a fresh-looking report over a stale boundary manufactures false trust, which is worse than no report.
- **Edit the changed section in place, don't rewrite the whole file** — anchor on the section heading. That keeps
  upkeep cheap on a long run. Reserve a full rewrite for a reconcile.
- **Full reconcile** (re-derive every line from durable state): on start/resume, at a phase boundary
  (setup → baseline → main loop, or a task handoff), and — since you have no persistent timer — whenever control
  returns from a long unattended command, plus a soft periodic check after a stretch of active work, so drift gets
  caught even in an unbounded loop.
- **Keep the `For the AI` section current.** When the evidence boundary shifts (new result files, new commands,
  new checkpoints), update its reconciliation checklist — it's the map the next model uses to recover after a reset.

## Writing it so a CEO trusts it

- **Gloss every term on first use** — including in the header lines, where the 30-second scan starts. The first
  time a model / dataset / method / metric appears, give it a ~4-word plain gloss, then use it freely. Jargon
  isn't banned; it's paid for on entry.
- **Tether findings to evidence, with an honest confidence label.** Define the labels so they can't inflate:
  *early* = seen once / not reproduced; *moderate* = reproduced once or corroborated by independent evidence;
  *strong* = reproduced under the intended comparison and not contradicted by known failures. Never write
  "improved / solved / on track" unless the evidence supports it.
- **Pick Health honestly.** `ON TRACK` only when there's an explicit success criterion and current evidence
  supports it; `UNKNOWN` when the goal, baseline, or evaluation isn't established yet; `WATCH` when evidence is
  mixed or thin; `BLOCKED` when stuck; `DONE` when the stated goal is met and verified against a named evidence
  boundary. In open-ended research there is often no "track" yet — say so.
- **Prefer `UNKNOWN` to optimistic filler.** Silence filled with hope is the exact failure the reader is exposed to.
- **Translate, don't duplicate.** If `autoresearch.md` / `TODO.md` already hold the technical state, lift the
  *meaning* into plain outcomes — don't paste experiment rows or checklist items, and don't keep two copies of a
  fact that will drift. Point at the other file instead.
- **One screen, and a snapshot — not a log.** It's a fixed-size briefing you overwrite, never a growing record: when a
  new finding outranks an old one, *replace* it (keep findings to ~3); there's no history section by design — history
  lives in your commits and results files. Before calling an update done, strip every `<placeholder>` and instruction
  phrase, then re-read only the first screen as if you'd never seen the project: if you can't answer *what / how's it
  going / what's been found / what's next / should I worry* without one unexplained term, fix the report, not the reader.

## Don't overlap

`STATUS.md` is the human-facing briefing — not the operator checklist (`todo` / `TODO.md`), the experiment-recovery
state (`autoresearch.md`), or a reformat of your last reply (`digest`). When those exist, update `STATUS.md` at the
*same checkpoints* they're updated (one cadence, not a competing one), write only CEO-facing sentences into it, and
let each file keep its own job.

## Optional helper

`scripts/status_check.py` (in this skill's own directory) does only the deterministic parts — never prose:

- `scaffold [path]` — write the template to `STATUS.md` if it's missing.
- `check [path] [--max-age-min N]` — verify the required sections (including `For the AI`) and freshness fields are
  present, the `Health` value is valid, no `<placeholders>` remain, and the report hasn't bloated (warns past ~one
  screen, fails past ~2×). With `--max-age-min` it also warns if `Fresh as of` is older than N minutes (off by
  default, since this skill is event-driven). Exits non-zero on a structural problem, so you can run it at a checkpoint
  as a self-gate: `python <this-skill-dir>/scripts/status_check.py check ./STATUS.md`.

The skill works without the script — it's a convenience, not a dependency. Write the `Fresh as of` time yourself
(e.g. from `date`); there's deliberately no auto-stamp, because a timestamp must only move when you've re-checked
the evidence boundary alongside it.

## Surviving a long run

A skill is just instructions, so a context compaction can summarize away the instruction to keep `STATUS.md` current. The
defense lives in the file, not in any harness machinery: the report survives on disk, the bootstrap has you read it on
resume, and its `For the AI` section restates the full discipline — so a model that **reads** it re-learns how to keep it
current even with the skill gone from context. The honest ceiling: nothing portable *forces* the reopen, so a fully
hands-off run never re-triggered between compactions can still drift — but the `Out of date if:` line keeps that drift
**visible**, and any model that reopens the file can **recover** the discipline.

## Worked example (what a filled first screen looks like)

```markdown
# STATUS — Teaching our spam filter to catch more fake reviews

Health: WATCH — best version beats the baseline, but the win is small enough it might be noise · Fresh as of: 2026-06-17 14:32 PT

## Bottom line
We're trying to catch more fake product reviews without wrongly flagging real ones. It's going okay: the
newest approach catches noticeably more fakes, but we're not yet sure the gain is real rather than luck.

## Should you be worried?
Mildly. The improvement has only shown up once — if it doesn't hold on a fresh batch of reviews (checking now),
the win may evaporate. No outside blocker.

## What we've found so far
- **Looking at *how* a review is written, not just the words, catches more fakes** — about 1 in 6 we used to miss.
  Checked against: experiment 21 in results.tsv. Confidence: moderate (beat baseline twice).
- **Bigger models didn't help** — the win came from better signals, not more horsepower. Saves money later.
  Checked against: experiments 8–12, all flat. Confidence: strong.

## Where we are
- Done: built the test setup; ran 21 experiments; found a clear front-runner.
- Now: re-checking the front-runner on reviews it has never seen.
- Next: if it holds, lock it in and write up.
- Needs a human? No.

## How current is this
Last checked against: experiment 21 in results.tsv, commit a1b2c3d.
Out of date if: results.tsv has experiment 22, or the fresh-batch run started at 14:30 has finished.

## For the AI — skip if you're the human
- You're maintaining this as a live plain-English briefing — a snapshot you overwrite, not a log; on resume, reconcile every section against reality before continuing, then keep it current (replace stale findings, don't accumulate).
- Update when a stakeholder answer changes (finding lands/reproduced/overturned, phase ends, blocker shifts, Health changes); edit the changed section and move the three freshness lines together; full reconcile on resume and when a long command returns.
- Health/confidence honestly: ON TRACK only with a met success criterion; early = seen once, moderate = reproduced/corroborated, strong = reproduced under the intended comparison.
- Check before trusting/continuing: results.tsv, run.log, git log --oneline -5
```
