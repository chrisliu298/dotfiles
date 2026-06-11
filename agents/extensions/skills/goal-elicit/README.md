# goal-elicit

> Interview a vague ask into a **verifiable goal artifact** — a Goal Contract (`GOAL.md`), a JSON
> checklist, or a phased design doc — then **stop**. It never executes the goal; it writes one file
> and hands off (to [goal-drive](../goal-drive/), or any agent).
>
> **`SKILL.md` is the authoritative spec** — this README is the picture. One source of truth for
> **Claude Code, Codex, and Grok** (no per-agent fork).

---

## The idea — separate *defining done* from *doing*

Most agents start coding before "done" is defined. goal-elicit does the opposite: a short,
disciplined interview that forces a fuzzy goal into a contract with **testable acceptance**, then
stops. Execution is a separate concern — its partner, goal-drive.

```
   vague ask
       │
       ▼
 ┌──────────────── goal-elicit ──────────────────┐
 │ Phase 0  triage   — Cynefin: how hard to ask  │
 │ Phase 1  orient   — restate the intent        │
 │ Phase 2  diverge  — widen; 2 interpretations  │
 │ Phase 3  converge — forced-choice decisions   │
 │ Phase 4  contract — show the compressed draft │
 │ Phase 5  confirm  — write status: ready       │
 └───────────────────────┬───────────────────────┘
                         ▼
               one artifact, then STOP
   GOAL.md · .goals/<id>.checklist.json · .goals/<id>.plan.md
                         │
                         ▼
            hand off → goal-drive (or any agent)
```

## What it produces — one artifact, chosen by triage

| Shape | File | When |
|---|---|---|
| **Contract** | `GOAL.md` (or `.goals/<id>.goal.md` for multiple) | the default — one deliverable |
| **Checklist** | `.goals/<id>.checklist.json` | enumerable, batchable items |
| **Phased doc** | `.goals/<id>.plan.md` | a staged build with per-phase acceptance |

Terminal states (frontmatter): **`ready`** (every `done_when` mapped to evidence, user assented) ·
**`blocked`** (round ceiling hit or missing context — `blocking_unknowns` lists what's needed) ·
**`draft`** (interview in progress; the file is the durable session state).

## The discipline (what keeps it honest)

- **Cynefin triage first** — Clear tasks get a fast lane (1 confirmation); Complicated get 3–5
  rounds; Complex get a probe contract. No interrogating a rename.
- **Forced-choice questions** — 2–4 labelled options with consequences, never yes/no theater. Uses
  Claude Code's `AskUserQuestion` when present; degrades to numbered plain text on Codex/Grok.
- **Hard gate on `done_when`** — every item names a command, file, metric, or observable behavior.
  No "looks good".
- **Hard cap: 8 rounds** — then a complete contract *or* an honest `blocked` brief. Never fakes done.
- **Writes one artifact and stops** — no planning, no code, no invoking other skills.

## Handoff & the optional `/goal` guardrail

The artifact is the handoff. For an executable, ready artifact, goal-elicit also emits a
ready-to-paste **`/goal`** block (advisory text — it never runs `/goal` itself):

- **Claude Code** — a `/goal` condition that watches the transcript for goal-drive's completion
  marker, pasted *before* goal-drive; a Stop hook keeps the session working until it appears.
- **Codex** — a one-line objective that **points at the artifact file**; Codex's own native `/goal`
  drives it to done (may need `codex features enable goals`).
- **Grok** — no `/goal`; just run goal-drive.

Mechanism, templates, and caveats: `references/goal-guardrail.md`.

## Files

| File | What |
|---|---|
| `SKILL.md` | the authoritative spec |
| `references/cynefin-triage.md` | Phase 0 decision tree + worked examples |
| `references/question-bank.md` | ~40 worked questions per taxonomy category |
| `references/contract-template.md` | the `GOAL.md` skeleton (+ optional `execution:` block) |
| `references/checklist-template.md` | the JSON checklist artifact |
| `references/phased-doc-template.md` | the phased design-doc artifact |
| `references/anti-patterns.md` | failure-mode table + the prompt move that prevents each |
| `references/goal-guardrail.md` | the optional `/goal` guardrail (Claude Code + Codex) |

## Invocation

`/goal-elicit <vague ask>` on Claude Code; invoke the **goal-elicit** skill by name on Codex/Grok.
Or just describe a fuzzy goal and let the agent reach for it. Triggers: "clarify what I want",
"define done/acceptance", "make this unambiguous", "plan this out", XY-problem requests.
