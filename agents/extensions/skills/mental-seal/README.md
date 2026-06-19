# mental-seal

> Hold **one** supreme priority front-of-mind for a whole task or session — a single visible,
> user-owned vow in `SEAL.md` that resists distraction and scope-drift and persists across context
> compaction. A working mechanism with a soul, not a sterile reminder.
>
> **`SKILL.md` is the authoritative spec** — this README is the picture. One source of truth for
> **Claude Code, Codex, and Grok** (hook-free on purpose). Adjacent to but distinct from
> [todo](../todo/) (many items), [exec-status](../exec-status/) (a briefing), and the memory system
> (many recalled facts).

---

## The idea — one vow, held as intent

A *mental seal* is the single non-negotiable commitment that governs which work you touch next.
It is pitched at the altitude of **commander's intent** — a *purpose + end-state*, not a procedure —
so the agent can re-route toward the same end when the plan breaks, and re-prioritize when the user
says so. It advises and surfaces; it never refuses the user.

The name is borrowed, deliberately, from the **Mental Seal (思想钢印)** in Liu Cixin's *The Dark
Forest* — a device that stamps an unshakeable judgment into a mind, and in the novel is *misused* to
implant a belief its subject can never question. This skill is the **inversion** of that cautionary
tale: the seal here is visible, singular, user-owned, releasable, and subordinate to the user and to
safety. That inversion *is* the guardrail design.

```
  set (user only)                        the seal lives at <project-root>/SEAL.md
        │                                         status: active
        ▼                                              │
  ┌──────────────── while active ────────────────┐     ▼
  │ persist   SEAL.md on disk (the Tablet)       │   ## History  ◄── released / superseded
  │ re-surface  anchor → re-read SEAL.md         │       (archived, never deleted)
  │ recall    Do-Confirm: "does this serve it?"  │
  │ conflict  surface, never silently override   │
  └───────────────────┬──────────────────────────┘
            ┌──────────┴───────────┐
            ▼                       ▼
     discharge_when met      user changes priority
     status: released        status: superseded → new active seal
```

## How recall survives — the Triad (no hooks)

| Layer | What | Cross-harness strength |
|---|---|---|
| **Tablet** | `SEAL.md` on disk at the project root | Equal on all three — a file always survives a reset |
| **Anchor** | one *static* sentinel line in `CLAUDE.md` + `AGENTS.md` pointing at the seal | Graded (see below) — installed once, never per-seal |
| **Wards** | in-context if-then rules (Gollwitzer) + a Do-Confirm check at decision points | The universal backbone — identical everywhere, no injection |

**The honest limit** — without a harness hook there is no *absolute* guarantee across a mid-session
auto-compaction. The anchor re-surfaces the recall instruction, but how reliably depends on the
harness:

| Harness | Instruction file | After a mid-session compaction |
|---|---|---|
| Claude Code | root `CLAUDE.md` | **Re-injected from disk** — verified (nested files aren't) |
| Codex | `AGENTS.md` | Built **once per session** — best-effort (issues #5772 / #8547) |
| Grok | `AGENTS.md` | Loaded at session start; post-compaction re-attach undocumented — best-effort |

So the durable floor is **Tablet + Wards** (work everywhere); the **Anchor** is a strong accelerator
on Claude and a best-effort one on Codex/Grok. The skill says this plainly rather than claiming a
uniform "always".

## One active seal at a time

By design — singularity is the whole point, not an incidental cap.

- **Within a project:** exactly one `status: active` seal. Re-sealing **supersedes** (the prior
  record moves to `## History`); it never stacks two active seals. Stacking co-equal imperatives is
  the deadlock failure the seal exists to prevent — if you want a ranked list of priorities, that is
  `todo`'s job.
- **Across projects:** one active seal *each* — scope is per-project, each root has its own
  `SEAL.md`. You can hold several at once globally, never two in one project.

## Setup — one-time, per project

The anchor is installed **once**, not per seal (that is what keeps it churn-free). With your OK, the
skill adds this dormant sentinel block to the project's instruction file(s) — to **both**
`CLAUDE.md` and `AGENTS.md` when the repo keeps both, mirrored identically:

```md
<!-- mental-seal:start -->
Mental seal: before substantial work, search upward to the project/git root for `SEAL.md`.
If it exists with `status: active`, read it, reconcile it against reality, and hold its
priority above scope-drift until released or superseded.
<!-- mental-seal:end -->
```

It is a no-op when no `SEAL.md` is active, so it stays put across seals — no add/remove churn on
tracked, `dfs`-synced docs. Decline the edit and the skill falls back to Tablet + Wards (best-effort
recall, zero footprint).

## The seal artifact — `SEAL.md`

| Field | Role |
|---|---|
| `id` | stable handle (`YYYY-MM-DD-slug`); `supersedes` + History reference it |
| `status` | `active` · `released` · `superseded` · `needs_review` |
| `priority` | the one sentence that governs everything |
| `purpose` / `end_state` | commander's intent — why, and what done looks like |
| `discharge_when` | the observable condition that releases the seal |
| `expires_if` | the staleness fuse — when to stop trusting it |
| `set_by` / `set_at` | provenance (never self-set silently) |
| `last_recalled` | stamped **only** during a reconcile that re-checked reality — never on a bare recall |

Body: a short **Litany** (the soul — recited at set / conflict / discharge, never every turn),
**Commander's intent** (purpose · end-state · non-goals), the **If-then wards** (the compliance
engine), and **History** (archived past seals). Template: `SEAL.template.md`.

## Guardrails — each inverts a cautionary source

| Failure mode | Source | Guard |
|---|---|---|
| Hidden imperative that fights the user | RoboCop Directive 4 | Plaintext, `set_by: user`, never self-set, always inspectable |
| Rigid override of legitimate re-prioritization | Asimov, "The Evitable Conflict" | Stores intent, not procedure; safety + explicit user instruction outrank it |
| Conflicting / stacked imperatives | geas tragedy / Asimov "Runaround" | Exactly one active seal; re-sealing supersedes with a reason |
| Stale seal treated as ground truth | Memento / *The Dark Forest* | `expires_if` + reconcile-on-resume → `needs_review`, not blind obedience |

**Real methodologies behind it** — implementation intentions (Gollwitzer, the if-then wards),
commander's intent & the decisive point (military doctrine), Ulysses pre-commitment (user-only
set/release), Gawande's do-confirm checklist (the recall gate), and the Bene Gesserit Litany Against
Fear (recitation as attention re-seating).

## Files

| File | What |
|---|---|
| `SKILL.md` | the authoritative operating spec (set / recall / conflict / discharge + guardrails) |
| `SEAL.template.md` | the `SEAL.md` artifact template — copied to the project root when a seal is set |
| `README.md` | this overview |

## Invocation

Trigger by description on all three agents — "mental seal", "seal this", "the one thing is…", "top
priority", "non-negotiable", "don't lose sight of this", or `/seal` on Claude Code. Recall is
**anchor-driven**, not an automatic session hook: a project's active seal re-surfaces via the
one-time anchor and the Wards, not by the skill auto-loading itself.
