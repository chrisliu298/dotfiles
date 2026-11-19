---
name: agent-team
description: Delegate read-only analysis, research, planning or review to the astra (Codex on Ark/方舟), sol (Codex on the subscription), claude, carbon (Gemini 4 Carbon) or neon (Gemini 4 Neon) backends, alone or in parallel, when the user asks for agent-team or names a backend; without named backends, pick them by difficulty. Not for simple tasks or a bare "subagent"/"子代理" (the host's native subagent), or implementation (codex-exec).
---

# Agent Team

Each backend runs its pinned model; no model or mode selection options are exposed. You choose
the reasoning effort for every `start` and `--once` with `--effort medium|high`: `medium` for bounded,
well-specified work (a focused question, a small diff, a lookup across known files),
`high` for open-ended or hard work (architecture, subtle correctness, debugging
without a reproduction, broad research). The user's explicit effort wins. Every backend runs with the
same full access as the user's own launchers: no approval prompts, no sandbox, and
network access (including SSH to dev machines). Read-only scope is an assignment
instruction, not a permission boundary. Default to a persistent session;
use `--once` only for a request that needs no follow-ups.

## Boundaries and completion

Use this for read-only assignments, not implementation, ChatGPT Pro, or a bare request for a
native subagent. Preserve the requested kind of
work; do not turn every assignment into review. Never substitute an unavailable backend.
A handle proves dispatch, and a finished turn still needs the requested deliverable.
Verify consequential claims against primary artifacts and preserve backend attribution.

The user's fixed form is `/agent-team ID ID ...` followed by the assignment, with ids
`astra` (方舟 GPT-6.2-Astra), `sol` (subscription GPT-6.2-Sol), `claude`, `carbon` (Gemini 4
Carbon) and `neon` (Gemini 4 Neon). Take those ids
literally: run exactly those backends, nothing added. Lines after it that start with `ID:` give
that backend its own assignment; every other line is shared, and backends without an `ID:` line
take the shared text as their assignment. An `ID:` line for a backend not on the first line is a
mistake to ask about, not a backend to add. Free-form wording still works through Choose
reviewers; there, GPT qualified by 方舟, Ark or Astra is `astra` alone, never `sol` plus `astra`.

## Rule of thumb when no backend is named

The user's named backends always win. When the user asks for agent-team (or a cross-model
second opinion) without naming backends, pick by difficulty:

- Simple: do not use agent-team; use the host's native subagent, or do it yourself.
- Medium: `astra`.
- Hard: `astra` and `neon`.
- Extremely hard: `astra`, `claude` and `neon`, all at `high`.

`carbon` runs only when the user names it: `neon` matches its score at `high` in under half the
time.

Tell the user which tier you judged and which backends that started.

How strong and fast each backend is at the two efforts this helper runs, from the Artificial
Analysis Intelligence Index (general reasoning, not a coding score; checked 2026-11-19). "min" is
the index's time per task, a relative wall-clock cost:

| Backend | Model | `medium` | `high` | Notes |
| --- | --- | --- | --- | --- |
| `neon` | Gemini 4 Neon | 55 (8 min) | 60 (15 min) | strongest here at `high`; weaker at `medium`, so prefer `high` |
| `carbon` | Gemini 4 Carbon | 58 (29 min) | 60 (34 min) | `neon`'s score at `high`, but over twice as slow |
| `sol` | GPT-6.2 Sol | 53 (3 min) | 55 (4 min) | fastest; subscription quota |
| `astra` | GPT-6.2 Astra | 52 (7 min) | 55 (9 min) | scores are GPT-6 Astra's (6.2 not yet measured); about Sol's level; Ark billing, not subscription quota |
| `claude` | Claude Opus 5.5 | 48 (7 min) | 52 (9 min) | gains most from effort (57 xhigh, 59 max), which this helper does not offer |

`sol` and `astra` are both OpenAI GPT models and tend to agree, as do `neon` and `carbon`;
`neon` and `claude` add independent views. One- or two-point gaps are within noise, so pick on independence, speed and
billing before score.

Resolve bundled references and `scripts/agent-team` from this skill root.
Assignments and task artifacts stay in their authorized cwd/scratch location.

## Read the relevant procedure before acting

- Before dispatch: read [Choose reviewers](references/choose-reviewers.md), then only the selected backend references linked there; preserve its assignment/file-sharing and capability rules.
- Before any helper action: read [Control and failure semantics](references/control-and-failures.md), including delivery receipts, ambiguous sends, bounded retries, interrupts and owned-session cleanup.
- Default persistent workflow, preparing an assignment, starting, supplementing, waiting or collecting: [Persistent tasks](references/persistent-tasks.md), together with the control procedure. Collect the same waiter to completion after each supplement.
- A backend's question (`[peer] agent-msg read ID` from a `*-review-*` session): [Persistent tasks](references/persistent-tasks.md#questions-from-backends).
- Only when no follow-up is needed: read [One-shot tasks](references/one-shot-tasks.md) before `--once`, together with selection, control and the shared assignment-preparation requirements in Persistent tasks; preserve partial results and do not rerun completed work.
- At task end: follow the control procedure's cleanup conditions. Stop only sessions you started; keep one open only for needed follow-ups and explicitly name it. Never stop the tmux server.
