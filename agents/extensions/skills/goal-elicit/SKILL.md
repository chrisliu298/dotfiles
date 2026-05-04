---
name: goal-elicit
description: |
  Conduct a structured multi-round interview that converts an ambiguous, high-impact,
  multi-step, delegated, autonomous, or execution-bound request into a verifiable Goal
  Contract before any planning, coding, subagent dispatch, or Codex /goal invocation.
  Use when the user asks to "clarify what I actually want", "define a goal/spec/done_when/
  acceptance criteria", "prepare this for /goal", "make this unambiguous", "interview me
  before we build", or "figure out what I'm building"; when the request looks like an XY
  problem; when success cannot yet be tested; or before atomic-push, subagent-executor,
  plan mode, /goal, or any long-running autonomous run on a request whose scope or
  verification is not already pinned down. Do NOT use for trivial reversible edits, simple
  factual questions, routine command execution, ordinary code review, or when the user has
  already supplied exact output and verification commands. The skill produces GOAL.md and
  either marks it ready_for_handoff or not_ready_blocked with open decisions listed.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash(git:*), Bash(date:*), AskUserQuestion
---

# goal-elicit

Convert an ambiguous request into a verifiable Goal Contract before action. The skill is the deliberate opposite of jumping to action: no planning, code, edits, or other-skill invocations until `GOAL.md` is written and the user has explicitly approved it (or the skill has terminated as `not_ready_blocked`).

Codex `/goal` keeps an agent looping toward an *already-defined* objective with a strict completion audit ("prompt-to-artifact checklist", "Do not accept proxy signals", "Treat uncertainty as not achieved"). It does almost no upstream elicitation. The quality of any long `/goal` run, plan-mode session, or subagent dispatch is gated by the quality of the contract handed to it. This skill writes that contract.

## What this skill produces

A single file: `GOAL.md` at the repo root (or `$PWD` if not in a git repo). Markdown with YAML frontmatter. Exactly one of three terminal states in the frontmatter:

- `ready_for_handoff` — every required field is filled, every `done_when` item is mapped to evidence, the user has explicitly assented.
- `not_ready_blocked` — interview hit the round ceiling or the user can't supply enough context. `blocking_unknowns` enumerates what's missing. Do not execute against a blocked contract.
- `draft` — interview in progress; the file is the durable session state.

Schema: see `references/contract-template.md`.

## Phase 0 — Triage (Cynefin)

Before asking a single question, classify the request. The triage decides how aggressive the interview is. See `references/cynefin-triage.md` for the decision tree and worked examples.

| Domain        | Signals                                                                          | Interview                                                                                  |
|---------------|----------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| Clear         | Obvious outcome and verification, single file, single-step, reversible.          | Fast lane: one confirmation, write a one-shot contract, done. `rounds_used: 1`.            |
| Complicated   | Knowable but under-specified, multi-step, has tradeoffs.                         | Standard interview, 3–5 user rounds.                                                       |
| Complex       | Outcome is partly emergent, no single right answer, exploratory or research.     | Exploration interview, 4–6 rounds. Contract describes the next safe **probe**, not a full implementation. Includes a learning criterion and rollback. |

If the request is Clear, do not run the full interview — it's a tax on simple work. Just confirm scope and write the contract. If you misclassify and find yourself asking a third question for what looked Clear, escalate to Complicated and continue.

## The interview

Five phases for Complicated/Complex domains. Round count below counts **user turns**, not assistant turns.

### Phase 1 — Orient (1 turn)

Restate the seed request neutrally. Maintain two distinct fields throughout: `stated_request` (verbatim) and `underlying_goal` (what the user is actually trying to achieve). Ask the smallest set of intent questions needed to populate `underlying_goal`.

Do **not** draft the contract yet. Open a scratch `GOAL.md` with `status: draft` and the YAML frontmatter only.

### Phase 2 — Diverge (1–3 turns)

Widen the frame so you are not anchored on the user's first wording. Cover: job-to-be-done, target user/stakeholder, current pain, prior attempts, anti-goals. Force decisions, not yes/no theater.

By the end of round 2, restate **at least two plausible interpretations** of the goal and ask the user which is right (or whether neither is). This breaks anchoring.

### Phase 3 — Converge (1–2 turns)

Present the leading interpretation, the unresolved choices, and your recommended defaults with rationale. Use this exact pattern when proposing an inference:

> "I infer X because Y. Plausible alternatives are A and B. Which is right?"

Use AskUserQuestion when there are 2–4 plausible options — make the options force a decision with consequences. Use free-text questions when the answer space is open. Both are fine; no single tool is required.

### Phase 4 — Contract (1 turn)

Show the draft `GOAL.md` in compressed form: objective, scope in/out, constraints, acceptance criteria (at least one as Gherkin), `done_when` (each item mapped to evidence), risks, rollback, handoff. Ask the user to **approve, edit, or mark blocked** — not yes/no.

### Phase 5 — Confirm (1 turn)

After incorporating the user's edits, write the final `GOAL.md` with `status: ready_for_handoff`. The final confirmation is *not* "are we good now?" It is:

> "I will write this as the Goal Contract unless you change one of these fields: [short list of decisions]."

## Question batching

- **3–5 questions per turn** by default. **Drop to 2** if any question is cognitively heavy.
- **Group by theme.** Examples: orient batch is "audience + outcome + deadline"; converge batch is "scope in + scope out + constraints"; contract batch is "acceptance + verification + rollback".
- **Every two rounds, post a running summary** with three sections: locked decisions, unresolved decisions, inferred defaults. The summary is also the diff with the previous summary — call out anything *changed or discarded*.

## Stop criteria

Mark `status: ready_for_handoff` only when **all** of the following are true. If any are false, either continue interviewing or write `status: not_ready_blocked`.

1. Required fields filled: `objective`, `underlying_goal`, `stakeholders`, `scope_in`, `scope_out`, `constraints`, `assumptions`, `acceptance_criteria`, `done_when` (each mapped to evidence), `verification_plan`, `risks`, `rollback`, `observability`, `handoff_targets`, `final_response_contract`.
2. At least one acceptance criterion is written as a Gherkin scenario (Given / When / Then) or an equivalent testable scenario.
3. **Hard gate:** every `done_when` item names a command, file artifact, metric, or user-observable behavior. Reject `done when "looks good"` style criteria.
4. Zero P0 open questions. Non-blocking assumptions are written with defaults and rationale.
5. The user has explicitly assented or supplied edits that you incorporated. Silence is not assent.
6. Contract audit: each acceptance criterion has a matching verification method; each constraint has a way to notice violation; no success criterion depends only on agent self-report. (This mirrors `/goal`'s own "do not accept proxy signals" rule.)

## Hard upper bound: 8 user rounds

| Round | Behavior                                                                                  |
|-------|-------------------------------------------------------------------------------------------|
| 1–5   | Normal interview.                                                                         |
| 6     | Warn the user: "Two rounds left before I either write the contract or write a `not_ready_blocked` brief." |
| 7     | Last chance to resolve P0 unknowns. Be explicit about what's still missing.               |
| 8     | Stop interviewing. Write either a complete contract or `not_ready_blocked` with `blocking_unknowns` populated. |

Never pretend completion to dodge the cap. A `not_ready_blocked` contract is a successful outcome — it tells the user (and any downstream agent) exactly what new input is required before execution can start.

## Question taxonomy

Ask in roughly this order. Earlier answers determine whether later categories matter. See `references/question-bank.md` for ~40 worked examples per category, each phrased to force a decision.

1. **Intent** — what outcome, for whom, why now?
2. **XY check** — what made you choose this requested approach? (Detects when stated_request ≠ underlying_goal.)
3. **Job-to-be-done** — "When [situation], I want [capability], so I can [outcome]."
4. **Stakeholders / decision owner** — who accepts the result?
5. **Scope in** — what must be included?
6. **Scope out / anti-goals** — what tempting adjacent work must not be done?
7. **Constraints** — stack, style, policy, time, budget, dependency, compatibility, security.
8. **Prior attempts and current state** — what exists, what failed, what should not be rediscovered?
9. **Success criteria** — what observable facts prove success?
10. **Definition of done** — what must be true before this is complete?
11. **Risks and edge cases** — what could make the apparent solution wrong?
12. **Rollback / containment** — how to undo, disable, or mitigate?
13. **Observability** — where will evidence appear (logs, tests, UI, files, metrics)?
14. **Deadline / sequencing** — real date or ordering constraint?
15. **Handoff target** — `/goal`, plan mode, subagents, atomic-push, manual?

## Anti-patterns to engineer out

See `references/anti-patterns.md` for the full failure-mode table with the prompt move that engineers each one out. The most important rules:

- **No yes/no until final approval.** Earlier questions must force a choice, rank, or edit.
- **No leading questions.** Always state your inference and evidence first, then ask the user to choose or correct it.
- **No faux confidence.** Maintain an explicit `open_questions` ledger in the draft `GOAL.md`. You may not say "I understand" until the ledger is empty or remaining items are marked non-blocking with defaults.
- **No "are we good now?" loops.** One confirmation protocol at Phase 5, not repeated checks.
- **No anchoring on first phrasing.** Preserve `stated_request` and `underlying_goal` as separate fields. By round 2, restate at least two plausible interpretations.
- **No verification theater.** Every `done_when` needs concrete evidence — command, file artifact, metric, or user-visible behavior.
- **No runaway scope.** Default new ideas to "Could" or "Won't this time" (MoSCoW) unless the user explicitly promotes them.
- **No premature commitment.** Do not invoke other skills, write code, or open another file (other than `GOAL.md`) until `status: ready_for_handoff` is written and the user has assented.

## Resumption

If `GOAL.md` already exists in the working directory:

1. Read it.
2. If `status: ready_for_handoff`, the contract is already complete. Tell the user, show the handoff menu (Phase 6), and stop. Do not re-interview.
3. If `status: draft` or `not_ready_blocked`, identify which fields are blank or in `blocking_unknowns`. Resume the interview by asking only for those fields. Do not re-ask filled fields. Increment `rounds_used` from where it left off.

## Phase 6 — Handoff (after `ready_for_handoff` is written)

Present a menu of paste-ready next steps based on `handoff_targets` in the frontmatter. Templates live in `assets/handoff-prompts/`. Read the template, substitute the contract path, and offer it to the user. Do **not** invoke `/goal`, plan mode, or other skills yourself — let the user choose.

| Target              | Template                                  | When                                                                |
|---------------------|-------------------------------------------|---------------------------------------------------------------------|
| Codex `/goal`       | `assets/handoff-prompts/codex-goal.md`    | Long-running autonomous execution by Codex.                         |
| Plan mode           | `assets/handoff-prompts/plan-mode.md`     | Decompose contract into an implementation plan in this session.     |
| `subagent-executor` | `assets/handoff-prompts/subagent-executor.md` | Multiple disjoint scope slices to execute in parallel.          |
| `atomic-push`       | `assets/handoff-prompts/atomic-push.md`   | Push only when every `done_when` item has its evidence verified.    |

Codex emphasis: **`/goal` is an execution loop, not a spec validator.** Do not invoke `/goal` at the end as verification. The contract audit (stop criterion 6 above) already mirrors `/goal`'s completion-audit logic; running it inside this skill is the verification step.

## What this skill must not do

- Do not plan, code, edit other files, or invoke another skill before `GOAL.md` is `ready_for_handoff`.
- Do not infer the user's goal silently and proceed.
- Do not pretend completion at the round ceiling — write `not_ready_blocked` instead.
- Do not invoke `/goal`, plan mode, `subagent-executor`, or `atomic-push` itself. Emit paste-ready prompts and let the user choose.
- Do not relay to Codex or GPT-Pro during the interview unless the user explicitly asks for an external second opinion.
- Do not over-question Clear-domain tasks. Fast-lane them.

## Files in this skill

- `SKILL.md` — this file.
- `references/contract-template.md` — the `GOAL.md` skeleton with all required frontmatter and body sections.
- `references/cynefin-triage.md` — Phase 0 decision tree with worked examples.
- `references/question-bank.md` — ~40 worked questions per taxonomy category.
- `references/anti-patterns.md` — full failure-mode table with the prompt move that engineers each one out.
- `assets/handoff-prompts/` — paste-ready handoff templates for each downstream target.

Read the references when you need them — not all up front. Long-form material is there so the model loads it only when relevant.
