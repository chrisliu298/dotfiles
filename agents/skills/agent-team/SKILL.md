---
name: agent-team
description: Delegate read-only analysis, research, planning or review to the gpt (Codex), ark (Codex on Ark/方舟), claude, carbon (Gemini 4 Carbon), hydro (Gemini 4 Hydrogen) or pro (ChatGPT Pro) backends, alone or in parallel, when the user names one. Not for implementation (codex-exec), pro alone (gpt-pro), or a bare "subagent"/"子代理" (native Agent tool).
---

# Agent Team

The user chooses the backend, not a model. Each backend runs its pinned model; no
model or mode selection options are exposed. You choose the reasoning effort for
every `start` and `--once` with `--effort medium|high`: `medium` for bounded,
well-specified work (a focused question, a small diff, a lookup across known files),
`high` for open-ended or hard work (architecture, subtle correctness, debugging
without a reproduction, broad research). The user's explicit effort wins. `pro`
takes no effort. Every backend runs with the
same full access as the user's own launchers: no approval prompts, no sandbox, and
network access (including SSH to dev machines). Read-only scope is an assignment
instruction, not a permission boundary. Default to a persistent session;
use `--once` only for a request that needs no follow-ups.

## Boundaries and completion

Use this for read-only assignments to the user's chosen backend(s), not implementation,
Pro alone, or a bare request for a native subagent. Preserve the requested kind of
work; do not turn every assignment into review. Never substitute an unavailable backend.
A handle proves dispatch, and a finished turn still needs the requested deliverable.
Verify consequential claims against primary artifacts and preserve backend attribution.

The user's fixed form is `/agent-team ID ID ...` followed by the assignment, with ids
`gpt` (subscription GPT-6.1-Sol), `ark` (方舟 GPT-6-Astra), `ark-sol` (方舟 GPT-6.1-Sol,
i.e. `ark` with `ARK_MODEL=sol`), `claude`, `carbon` (Gemini 4 Carbon), `hydro` (Gemini 4
Hydrogen) and `pro`. Take those ids
literally: run exactly those backends, nothing added. Lines after it that start with `ID:` give
that backend its own assignment; every other line is shared, and backends without an `ID:` line
take the shared text as their assignment. An `ID:` line for a backend not on the first line is a
mistake to ask about, not a backend to add. Free-form wording still works through Choose
reviewers; there, GPT qualified by 方舟, Ark or Astra is `ark` alone, never `gpt` plus `ark`.

Resolve bundled references and `scripts/agent-team` from this skill root.
Assignments and task artifacts stay in their authorized cwd/scratch location.

## Read the relevant procedure before acting

- Before dispatch: read [Choose reviewers](references/choose-reviewers.md), then only the selected backend references linked there; preserve its assignment/file-sharing and capability rules.
- Before any helper action: read [Control and failure semantics](references/control-and-failures.md), including delivery receipts, ambiguous sends, bounded retries, interrupts and owned-session cleanup.
- Default persistent workflow, preparing an assignment, starting, supplementing, waiting or collecting: [Persistent tasks](references/persistent-tasks.md), together with the control procedure. Collect the same waiter to completion after each supplement.
- A backend's question (`[peer] agent-msg read ID` from a `*-review-*` session): [Persistent tasks](references/persistent-tasks.md#questions-from-backends).
- Only when no follow-up is needed: read [One-shot tasks](references/one-shot-tasks.md) before `--once`, together with selection, control and the shared assignment-preparation requirements in Persistent tasks; preserve partial results and do not rerun completed work.
- At task end: follow the control procedure's cleanup conditions. Stop only sessions you started; keep one open only for needed follow-ups and explicitly name it. Never stop the tmux server.
