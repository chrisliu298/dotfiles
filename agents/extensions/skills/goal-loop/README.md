# goal-loop

**Turn a fuzzy request into finished, reviewed work — and only weigh in on the decisions that matter.**

You describe what you want. goal-loop writes a clear spec, implements it, gets the work reviewed by
several AI models, and then does the tedious part for you: it **sorts the ~83% of review
comments that are out-of-scope noise or don't apply out of your way** (recorded, not lost), and shows
you only the **small handful that are genuinely actionable**. You pick which of those to fix; it makes the fixes and re-reviews — repeating
until you're satisfied. It never blindly applies a review comment, because that was measured to be
unsafe (a reviewer can confidently flag the wrong thing).

It's a thin coordinator over three skills you may already use — **goal-elicit** (clarify the goal),
**goal-drive** (build it), and **prism** (multi-model review).

---

## The workflow

```
   you ──▶ /goal-loop -- "add a --dry-run flag to the deploy script"
              │
   ┌───────────────────────────────────────────────────────────────┐
   │  1. goal-elicit   writes a clear spec                         │
   │  2. prism reviews the SPEC (default; --no-spec-review to skip)│
   │  3. goal-drive    implements it                               │
   │  4. prism         reviews the IMPLEMENTATION                  │
   │  5. goal-loop     auto-drops the noise (out-of-scope, N/A),   │
   │                   shows you only the actionable few ★         │
   │  6. YOU           pick which to fix (or defer / stop)         │
   │  7. goal-drive    applies your picks                          │
   │  └─ back to 4 (re-review) … until done                        │
   └───────────────────────────────────────────────────────────────┘
              │
              ▼
          DONE ✓
       ★ = the one place it asks you: which findings are worth fixing
```

Each step is one turn, and progress lives on disk — if your session ends or gets summarized, just run
`/goal-loop continue` and it picks up where it left off.

---

## Quick start

```
/goal-loop -- add a --dry-run flag to the deploy script
```

Useful options:

```
/goal-loop --prism "2 m" -- harden the auth module      # how thorough each review is
/goal-loop --no-spec-review -- <request>                # skip the default spec review (trivial goals)
/goal-loop --max-rounds 3 -- <request>                  # cap the review→fix rounds
/goal-loop --auto --prism "2 m" -- <request>            # run unattended (overnight) — no questions
/goal-loop continue                                     # resume an interrupted loop
```

You don't have to choose the review depth up front — if you omit `--prism`, goal-loop asks you *after*
the build, when you can see how thorough the review needs to be.

---

## Run it overnight (`--auto`)

By default goal-loop asks you two things: sign off the spec, and pick which findings to fix. `--auto`
removes both so it can run **unattended** — pair it with Claude Code's native `/goal` and go to sleep:

```
/goal "Drive .goals/<id>.goal.md id <id> through goal-loop --auto; resume with `goal-loop continue <id>`. SATISFIED on a line beginning 'GOAL-LOOP AUTO-COMPLETE: <id>', 'GOAL-LOOP AUTO-HANDOFF: <id>', or 'GOAL-LOOP AUTO-HALTED: <id> —' with a 'GOAL-LOOP AUTO EVIDENCE-END' line + real verification output earlier. TIMEOUT after <N> turns."
```

What you wake up to: the implementation built and reviewed, the **safe** fixes already applied, and a
tight, pre-sorted **decision queue** in `.goals/<id>.auto-report.md` for the calls that genuinely need
your judgment. What `--auto` will **not** do is make those scope calls for you — it only auto-applies a
fix when a *frozen, pre-signed test for an existing acceptance criterion was failing and the fix makes it
pass*. With no such tests it auto-fixes nothing and just hands you the queue — that's the safe default,
not a bug. (Power-user mechanism: [`references/loop-protocol.md`](references/loop-protocol.md) § Autonomous mode.)

---

## Good to know

- **You decide what gets fixed — it never blind-applies.** The loop sorts every review finding for you:
  noise and out-of-scope ideas are deferred (you never see them), genuine scope questions stop and wait,
  and only the small actionable batch is shown for your call. That human step is the safety floor — a
  reviewer can flag something real that's actually out of scope, or wrong-in-context, and only you can
  tell.
- **Your spec is the boss.** Once set, review comments can't quietly rewrite the goal; fixes go into
  separate per-round files. The loop is "done" when *your* acceptance criteria are met.
- **A better spec means fewer interruptions.** The up-front spec review is **on by default**
  (`--no-spec-review` to skip; auto-skipped for trivial goals) — it makes your acceptance criteria more
  complete, so more later findings are clearly actionable.
- **Built for Claude Code.** goal-loop is installed for Claude Code — its review backend is prism and
  `--auto` rides the native `/goal` command, both Claude-only. The skill body is written runtime-neutrally
  and the artifacts it produces are portable, but if you run the loop off-Claude the multi-model review
  degrades: it writes out a review request for you to run from Claude, or falls back to single-model review
  (and `--auto` does no auto-fix without cross-model review).
- **It won't run away.** At most 2 review→fix rounds by default (`--max-rounds`), and it stops early if
  the same issue keeps coming back.

---

## Related — `/goal` vs `/goal-elicit` vs `/goal-drive` vs `/goal-loop`

Four similar names, four different jobs. The short version: **native `/goal` is the *engine* that keeps your
agent working; the three `goal-*` skills are the *work*.**

| | What it is | What it does |
|---|---|---|
| **native `/goal "<cond>"`** | a built-in Claude Code command (not a skill) | keeps the session taking turns until your condition shows up in the transcript — the thing that makes any run go *unattended* |
| **`/goal-elicit`** | skill | interviews you and writes a clear, verifiable **spec**, then stops — no building |
| **`/goal-drive`** | skill | **builds** an existing spec to verified-done, no questions, stops only on real exceptions — no review |
| **`/goal-loop`** | skill | **builds + gets it reviewed by several models + iterates** (elicit→drive→review→fix); `--auto` runs it unattended |

How they fit together:

- **Pipeline:** `/goal-elicit` writes the spec → then `/goal-drive` (just build it) **or** `/goal-loop`
  (build *and* review-iterate). goal-loop is the only one that adds the multi-model review loop; it reuses
  goal-elicit and goal-drive rather than reimplementing them.
- **Wrap any of them in native `/goal`** to run across turns without re-prompting — e.g.
  `/goal "drive <artifact> with goal-drive until it prints GOAL-DRIVE COMPLETE…"`, or the `--auto` form above
  for an unattended *reviewed* loop. (`/goal` judges only what's printed to the transcript, never your files.)
- **Mnemonic:** elicit = *what* · drive = *do it* · loop = *do it well* (with review) · native `/goal` = *keep
  going* until done. (`prism` — the multi-model review goal-loop calls — is also usable on its own for a one-off review.)

Power-user details: [`SKILL.md`](SKILL.md) and [`references/loop-protocol.md`](references/loop-protocol.md).
The `scripts/` harnesses (`empirical_gate.py`, `oracle_gate.py`) are the evidence for *why* the human
stays in the loop — and the one path that could safely remove it.
