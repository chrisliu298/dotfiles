---
effort: low
description: |
  Hold ONE supreme priority front-of-mind for a whole task or session — a single
  visible, user-owned vow in SEAL.md that resists distraction and scope-drift and
  persists on disk across context compaction. Use when the user says "mental seal",
  "seal this", "the one thing", "top priority", "non-negotiable", "hold this above
  all", "don't lose sight of this", or "/seal"; and when a project's SEAL.md is
  active (recall is anchor-driven, not an automatic session hook). Maintain
  exactly one active seal; recall it at decision points; surface conflicts instead of
  silently obeying; discharge only on verified completion, expiry, or explicit user
  resealing. NOT a task list (use todo), a stakeholder briefing (use exec-status), a
  recurring heartbeat (keep-warm), or a fact store (memory) — it is one always-present
  priority anchor with first-class enforcement and release semantics.
user-invocable: true
---

# Mental Seal

Hold one supreme priority — the agent's single vow for this task or session — and keep it front-of-mind no matter how far the work drifts. The seal lives in one visible `SEAL.md` at the project root: a durable, user-owned commitment that outranks scope-drift and tempting side-quests until it is verified, released, or deliberately replaced.

The name is borrowed, deliberately, from the *Mental Seal* (思想钢印) in Liu Cixin's *The Dark Forest* — a device that stamps an unshakeable judgment into a mind, and in the novel is **misused** to implant a belief its subject can never question. This skill is the inversion of that cautionary tale: the seal here is **visible, singular, user-owned, releasable, and subordinate** to the user and to safety. A seal you cannot see, change, or release is the failure mode, not the goal.

This is not the native in-session checklist and not `todo`. `TODO.md` is many durable items; a seal is the *one* priority that governs which of those items you touch next. Use both at the right altitude.

## When to use

Reach for a seal when one priority must dominate a long or drift-prone stretch of work:

- The user invokes it — "seal this", "the one thing is…", "top priority", "non-negotiable", "don't lose sight of this", "/seal".
- A long autonomous run risks wandering off the one outcome that matters.
- When the project's recall anchor points you to an active `SEAL.md` — on session start, resume, or after a compaction.

Skip it when:

- The work is a one-shot edit, a quick question, or comfortably tracked by the native checklist.
- There are genuinely several co-equal priorities — a seal is *one* thing. Force the single controlling priority, or decline and use `todo` for a list.
- `pwd` is `$HOME`, a tmp dir, or has no clear project root — ask where the seal should live rather than guessing.

## The seal artifact

One file, `SEAL.md`, at the project root. A template lives beside this skill as `SEAL.template.md` — copy it (don't retype it) and fill it in. The shape:

- **Frontmatter** — the lifecycle and provenance: `status`, `scope`, `set_by`, `set_at`, `priority` (one sentence), `purpose`, `end_state`, `discharge_when`, `expires_if`, `supersedes`, `last_recalled`, `last_recalled_against` (what the last reconcile checked against — set together with `last_recalled`, never alone).
- **Litany** — the soul: a compact first-person vow, recited at set / conflict / discharge, *not* every turn. It ends in action (the path that serves the seal wins; everything else waits) — a focusing phrase, never genre cosplay.
- **Commander's intent** — purpose, end state, and **non-goals** (the scope fence). The seal stores *intent*, not a procedure, so the agent can re-route toward the same end when the plan breaks — and re-prioritize when the user says so.
- **If-then wards** — explicit cue→response rules ("IF about to edit/finalize → THEN check the seal"). This is the part that actually changes behavior; keep it in working memory.

Keep the whole file short enough to re-read in seconds. Long rationale belongs in linked tickets or a design doc, not in the seal.

## How recall survives — the mechanism

Three layers, each covering a different way the priority gets lost. **No harness hooks** — every layer works on Claude, Codex, and Grok, but the cross-compaction strength is *graded* (see the honest limit), so don't lean on any single layer as a universal guarantee.

1. **The Tablet — `SEAL.md` on disk.** Survives session boundaries and compaction because it is a file, not a memory of one — the externalized-memory pattern (the same reason `todo`/`exec-status` survive a reset). This is the one layer that is equally durable on all three harnesses.

2. **The Anchor — one permanent line in the project's instruction file(s)** (`CLAUDE.md` *and* `AGENTS.md`). It points at the seal; it is installed **once** per project as a static, dormant sentinel block (see Setup) and is a no-op when no seal is active. The skill never edits these files per-seal — across a seal's whole lifecycle it only ever writes `SEAL.md`. The anchor re-surfaces the *recall instruction* after a context reset, but how reliably depends on the harness:

   | Harness | Instruction file | After a mid-session compaction |
   |---|---|---|
   | Claude Code | root `CLAUDE.md` | **Re-injected from disk** — verified (nested files are not) |
   | Codex | `AGENTS.md` | Built **once per session**; a mid-session edit isn't re-read until the next session — best-effort (issues #5772 / #8547) |
   | Grok | `AGENTS.md` | Loaded at session start; post-compaction re-attach is undocumented — best-effort |

   Because the anchor is static and added before work, it loads on every harness at session start; the weak case is only a *mid-session* compaction on Codex/Grok, where it may not re-surface until the next session.

3. **The Wards — in-context discipline.** The if-then wards and the Do-Confirm check (below) carry salience *between* resets and through long autonomous tool-loops where no new prompt fires. This is the compliance engine, it needs no injection, and it behaves identically on all three harnesses — so it, not the anchor, is the universal backbone.

**The honest limit:** without a harness hook there is no mechanical guarantee across a mid-session auto-compaction. On Claude the root-`CLAUDE.md` anchor makes recall robust; on Codex and Grok it is best-effort — the same honest ceiling `exec-status` admits ("nothing portable forces the reopen"). The durable cross-harness floor is layer 1 (the file always survives on disk) plus layer 3 (re-read `SEAL.md` at the next substantial-work check); treat the anchor as an accelerator on top of that floor, not the guarantee.

### Setup (one-time, per project)

The anchor is installed **once** per project, not per seal — that is what keeps it churn-free. With the user's OK, add this sentinel block to the project's instruction file(s) — to **both** `CLAUDE.md` and `AGENTS.md` when the repo keeps both, with identical text (honor the repo's own doc-sync rule):

```md
<!-- mental-seal:start -->
Mental seal: before substantial work, search upward to the project/git root for `SEAL.md`.
If it exists with `status: active`, read it, reconcile it against reality, and hold its
priority above scope-drift until released or superseded.
<!-- mental-seal:end -->
```

It is dormant when no `SEAL.md` exists, so it stays in place across seals — install it once, then leave these files alone. If the user declines to edit tracked instruction files, skip the anchor and rely on layers 1 + 3 (best-effort recall, zero footprint). Never add or remove this block on set/discharge: per-seal churn on tracked, `dfs`-synced docs collides with concurrent sessions and this repo's doc-sync rule.

## The discipline

### Set

Only from explicit user intent — never self-seal silently. Distill the request to exactly one priority; if it is ambiguous or names several priorities, ask once for the single controlling one. (If your harness has a structured-question tool, use it; otherwise present numbered options inline and accept a number/letter reply.) Then: copy `SEAL.template.md` to the project root as `SEAL.md`, fill every field (give it a stable `id`), set `set_by` to the user and `set_at` to today, and recite the litany once to confirm the vow. The recall anchor is a **one-time per-project setup** (see Setup), not something you write per seal — if the project has no anchor yet, offer to install it once. If a seal is already active, do not stack a second — `supersede` the old one (move its full record to `## History` with the date and reason) or decline.

### Bootstrap (session start / resume / after compaction)

Before substantial work, **search upward from the current directory to the project/git root** for `SEAL.md` — it lives at the project root, so a bare `./SEAL.md` check misses it from a subdirectory. If it exists and `status: active`:

1. Read it. Re-state the `priority` in one line to re-seat it.
2. **Reconcile against reality** — if the code/state shows the priority is already met, or the work has moved past it, surface the drift to the user; mark `status: needs_review` rather than obeying a stale seal. (Externalized memory can be wrong — never treat the file as sacred.) Stamp `last_recalled` to today *as part of this reconcile* — only here, where you actually re-checked the seal against reality, never on a bare recall (a fresh timestamp over an unchecked seal manufactures false trust). If you can run the helper, `<this-skill-dir>/scripts/docmaint stamp --attest reconciled --checked-against "<what you checked>"` sets `last_recalled` + `last_recalled_against` together and records a checkpoint, so a later edit to the seal's substance without a fresh reconcile is caught by `docmaint check --handoff`.

### Recall (Do-Confirm at decision points)

Before planning, a major edit or tool batch, a change of direction, or a final answer, run a one-line internal check: **does this action advance, protect, or discharge the seal?** If yes, proceed. If no, name the drift and defer it. Keep the check internal — surface the seal to the user only when it changes what you do, prevents drift, or needs their call. Do not narrate the litany on every turn.

### Conflict (never silently override)

If a fresh request, a discovered fact, or a tempting improvement conflicts with the seal, **stop and name the conflict**: "This competes with the active seal because X — keep the seal and defer this, suspend it once, or supersede it?" The seal is subordinate to system/developer safety constraints and to explicit user re-prioritization; it outranks only drift and convenience. It advises and surfaces; it never refuses the user.

### Discharge

When `discharge_when` is verified met, set `status: released`, add the date and the evidence, and move the full record to `## History`. **Leave the project's recall anchor in place** — it is dormant without an active `SEAL.md` and is shared per-project, not per-seal. If the user changes the priority, mark the old seal `superseded` (its record goes to `## History`, referenced by `id`) and set the new active seal. Never silently ignore an active seal, and never delete a discharged one — archive it.

## Optional helper

`scripts/docmaint` (beside this skill) is a stdlib-only helper that `todo`, `exec-status`, and `mental-seal` all share with the **same verbs** — `locate · scaffold · check · sync · stamp · print · self-test` (exit `0` ok · `1` stale under `--handoff` / missing under `--required` · `2` malformed). It is a pure accelerator: the seal's actual mechanism is the file on disk plus the in-context wards (the hook-free floor in *How recall survives*), and the skill works with **zero** script. `docmaint` only does the deterministic parts, and auto-locates `SEAL.md` by searching upward to the project/git root (so it works from any subdirectory):

- `scaffold` — copy `SEAL.template.md` to the project root if `SEAL.md` is missing (you still fill every field by hand from explicit user intent).
- `check [--handoff] [--required] [--strict-anchor]` — validate the lifecycle invariants: required frontmatter, a valid `status`, **exactly one active seal**, no `<placeholders>` in an active seal, and the recall-freshness checkpoint (below). The `mental-seal` anchor's presence in `CLAUDE.md`/`AGENTS.md` is a warning by default, a failure under `--strict-anchor`.
- `sync` — refresh only a hidden, mechanical `validated_at` comment; it never touches the vow, the lifecycle fields, or `last_recalled`.
- `stamp --attest reconciled --checked-against "<evidence>"` (alias: `--against`) — the **only** verb that moves `last_recalled`. The evidence flag is `--checked-against`, the same name `exec-status` uses (so the flag is consistent across docs). It sets `last_recalled` to today and `last_recalled_against` from your argument, and records a content-hash checkpoint over the seal's substance — `priority`/`purpose`/`end_state`/`discharge_when`/`expires_if`/`status` and the body, with the archival `## History` section excluded (editing old records won't flag the active seal). This is how auto-stamping stays *honest*: the tool writes the date, but only inside your explicit attestation that you reconciled the seal against reality — and any later edit to that substance (even a hand-bumped `last_recalled`) makes `check --handoff` fail until you re-`stamp`. The checkpoint is **tamper-evident, not tamper-proof** (it catches honest drift, not a deliberately rewritten hidden hash). Never run it on a bare recall.

The script never *invents* recall freshness — a bare `check`/`sync` will not move `last_recalled`; only an attested `stamp` does. It writes only `SEAL.md` (never the instruction-file anchor — that stays a one-time manual Setup). `docmaint self-test` verifies it. This keeps the skill universal: an agent whose harness can't run the script maintains `SEAL.md` and `last_recalled` by hand, exactly as before.

## Guardrails

Each one inverts a specific cautionary source:

| Failure mode | Cautionary source | Guard |
|---|---|---|
| Hidden imperative that fights the user | RoboCop Directive 4 | Seal is plaintext, `set_by: user`, never self-set, always inspectable |
| Rigid override of legitimate re-prioritization | Asimov's "The Evitable Conflict" | Stores intent/end-state, not procedure; safety + explicit user instruction outrank it; advises, never blocks |
| Conflicting / stacked imperatives, deadlock | geas tragedy / Asimov's "Runaround" | Exactly one active seal; re-sealing supersedes with a recorded reason |
| Stale seal treated as ground truth | Memento / *The Dark Forest* | `expires_if` + reconcile-on-resume → `needs_review`, not blind obedience |
| Ritual theater that doesn't survive a session | — | The durable guarantee is the file on disk + the in-context wards; the litany is salience only, recited sparingly |
| Standing context pollution | — | One static dormant anchor per project (installed once, never per-seal) + no per-turn injection — zero recurring footprint, no `dfs`/merge churn |

## Why this design

- **One file, one vow.** A single canonical seal can't suffer the "forgot to check the other place" failure, and singularity is the whole point — working memory holds one supreme priority, not five.
- **Intent, not procedure.** Commander's-intent framing lets the agent improvise toward the same end when the plan breaks, and re-prioritize when the user redirects — the property a hardcoded directive destroys.
- **If-then carries compliance; the file carries memory.** Salience (the priority being present) is not the same as compliance (acting on it). The wards (cue→response) are what actually bend behavior; the file and anchor only have to solve forgetting.
- **Hook-free on purpose.** A harness hook would give a harder mid-compaction guarantee but only on Claude — it would make the skill Claude-only in substance. The hook-free design keeps it universal; the cost, stated honestly, is best-effort mid-compaction recall on Codex/Grok (the file and the wards still hold everywhere).

## Gotchas

- **Don't self-seal.** A seal is set from explicit user words, not the agent's inference of what matters. Propose one if a long task is drifting, but let the user set it.
- **Don't let it fight the user.** If the seal and a fresh instruction collide, surface it and let the user decide — never enforce the seal over their explicit redirection.
- **Don't stack seals.** Two co-equal seals is the deadlock failure. One active seal; supersede to change it.
- **Don't trust a stale seal.** On resume, reconcile before relying. If the work has outgrown it, `needs_review`, don't obey.
- **Don't spam the litany.** Recite it at set / conflict / discharge. Between those, the seal works silently through the Do-Confirm check.
- **Don't churn the anchor.** Install it once per project (Setup); never add or remove it on set/discharge — that dirties tracked, `dfs`-synced docs and collides with concurrent sessions.
- **After a compaction, re-read rather than trust memory.** If context was summarized and you've lost the priority, search up to the project root for `SEAL.md` and re-read before acting; the `rehydrate` skill can recover other dropped detail.
- **Don't place it outside a project root.** If there's no clear project, ask where the seal belongs before writing anything.
