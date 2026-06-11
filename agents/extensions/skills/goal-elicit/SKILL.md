---
name: goal-elicit
description: |
  Interview the user and write a verifiable goal artifact — a Goal Contract (GOAL.md), a
  JSON checklist, or a phased design doc, chosen by triage. Never executes the goal or
  invokes downstream tools — it writes the artifact and stops; hand off to goal-drive (or
  any agent) to execute. Use for "clarify what I want", "define done_when/acceptance
  criteria", "make this unambiguous", "plan this out", XY-problem requests, or untestable
  success. Skip trivial edits, factual questions, routine commands, and code review.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash(git:*), Bash(date:*), AskUserQuestion
---

# goal-elicit

Interview the user and write a verifiable goal artifact. The deliverable is a single file, chosen by triage — a Goal Contract (`GOAL.md`), a JSON checklist, or a phased design doc. The skill terminates when that artifact is written — the user takes it from there and hands it to whichever agent or tool pursues it (e.g. [[goal-drive]]).

This skill never plans, edits other files, runs code, or invokes other skills. It writes one artifact and stops.

## What this skill produces

**One artifact**, chosen by triage (Phase 0), then the skill stops:

- **Contract** — `GOAL.md` at the repo root (or `$PWD` if not in a git repo). The default shape. Schema: `references/contract-template.md`.
- **Checklist** — `.claude/goals/<id>.checklist.json` for enumerable, batchable work. Schema: `references/checklist-template.md`.
- **Phased doc** — `.claude/goals/<id>.plan.md` for staged builds with per-phase acceptance. Schema: `references/phased-doc-template.md`.

The contract carries one of three terminal states in its frontmatter (the checklist/phased shapes carry the analogous per-unit state — see their templates):

- `ready` — every required field is filled, every `done_when` item is mapped to evidence, the user has explicitly assented. The artifact is ready to use.
- `blocked` — interview hit the round ceiling or the user can't supply enough context. `blocking_unknowns` enumerates what's missing. Tell the user the artifact is incomplete and what is needed.
- `draft` — interview in progress; the file is the durable session state.

Execution is **out of scope** — a separate skill, goal-drive, drives any of these artifacts to done. goal-elicit writes the artifact and stops; it never invokes goal-drive.

## Phase 0 — Triage (Cynefin)

Before asking a single question, classify the request. The triage decides how aggressive the interview is. See `references/cynefin-triage.md` for the decision tree and worked examples.

| Domain        | Signals                                                                          | Interview                                                                                  |
|---------------|----------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| Clear         | Obvious outcome and verification, single file, single-step, reversible.          | Fast lane: one confirmation, write a one-shot contract, done. `rounds_used: 1`.            |
| Complicated   | Knowable but under-specified, multi-step, has tradeoffs.                         | Standard interview, 3–5 user rounds.                                                       |
| Complex       | Outcome is partly emergent, no single right answer, exploratory or research.     | Exploration interview, 4–6 rounds. Contract describes the next safe **probe**, not a full implementation. Includes a learning criterion and rollback. |

If the request is Clear, do not run the full interview — it's a tax on simple work. Just confirm scope and write the contract. If you misclassify and find yourself asking a third question for what looked Clear, escalate to Complicated and continue.

Triage also selects the **work shape** — which artifact to write (contract / checklist / phased doc) — orthogonally to the domain. See the "Work shape" section in `references/cynefin-triage.md`. Default to a contract; promote to a checklist (enumerable, script-generatable items) or a phased doc (staged build with per-phase acceptance) only on a clear signal.

## The interview

Five phases for Complicated/Complex domains. Round count below counts **user turns**, not assistant turns.

### Phase 1 — Orient (1 turn)

Restate the seed request neutrally. Maintain two distinct fields throughout: `stated_request` (verbatim) and `underlying_goal` (what the user is actually trying to achieve). Ask the smallest set of intent questions needed to populate `underlying_goal`.

Do **not** draft the contract yet. Open a scratch artifact with `status: draft` and the frontmatter only — `GOAL.md` by default, switching to the checklist/phased path under `.claude/goals/<id>.` once triage picks the work shape.

### Phase 2 — Diverge (1–3 turns)

Widen the frame so you are not anchored on the user's first wording. Cover: job-to-be-done, target user/stakeholder, current pain, prior attempts, anti-goals. Force decisions, not yes/no theater.

By the end of round 2, restate **at least two plausible interpretations** of the goal and ask the user which is right (or whether neither is). This breaks anchoring.

### Phase 3 — Converge (1–2 turns)

Present the leading interpretation, the unresolved choices, and your recommended defaults with rationale. Use this exact pattern when proposing an inference:

> "I infer X because Y. Plausible alternatives are A and B. Which is right?"

Use AskUserQuestion when there are 2–4 plausible options — make the options force a decision with consequences. Use free-text questions when the answer space is open. Both are fine; no single tool is required.

### Phase 4 — Contract (1 turn)

Show the draft artifact in compressed form: objective, scope in/out, constraints, acceptance (at least one Gherkin, or per-item/per-phase acceptance for checklist/phased), `done_when` (each item mapped to evidence), risks, rollback. Ask the user to **approve, edit, or mark blocked** — not yes/no.

### Phase 5 — Confirm (1 turn)

After incorporating the user's edits, write the final artifact with `status: ready`. The final confirmation is *not* "are we good now?" It is:

> "I will write this as the goal artifact unless you change one of these fields: [short list of decisions]."

If the contract's `execution.commit_policy` is `per_unit`, call it out explicitly — with that setting the executor makes a local commit per verified unit without asking each time.

Once the file is written, tell the user where it is (path) and stop. The user takes it from there.

**Optional `/goal` guardrail (Claude Code only).** If the artifact is *executable and ready* — a
contract with an `execution:` block, a checklist with non-empty `items`, or a phased doc with a
`## Phases` section (an `authority` block is optional for all of these) — also emit a
ready-to-paste `/goal "..."` block for the user to run *before* goal-drive. It keeps the
session working until goal-drive prints its completion marker, and treats a by-exception stop as
terminal too. Fill the condition template from `references/goal-guardrail.md` using the artifact's
`done_when`/acceptance and the terminal markers (it also gives the per-shape "ready" test and the
emit/skip gates). Emitting the text is **not** execution — goal-elicit never runs `/goal` or any
hook. Skip it for Clear one-shot goals, for `blocked`/`draft` artifacts, and on Codex (no `/goal`);
it degrades to inert advisory text.

## Question batching

- **3–5 questions per turn** by default. **Drop to 2** if any question is cognitively heavy.
- **Group by theme.** Examples: orient batch is "audience + outcome + deadline"; converge batch is "scope in + scope out + constraints"; contract batch is "acceptance + verification + rollback".
- **Every two rounds, post a running summary** with three sections: locked decisions, unresolved decisions, inferred defaults. The summary is also the diff with the previous summary — call out anything *changed or discarded*.

## Stop criteria

Mark `status: ready` only when **all** of the following are true. If any are false, either continue interviewing or write `status: blocked`.

1. Required fields filled: `objective`, `underlying_goal`, `stakeholders`, `scope_in`, `scope_out`, `constraints`, `assumptions`, `acceptance_criteria`, `done_when` (each mapped to evidence), `verification_plan`, `risks`, `rollback`, `observability`, `final_response_contract`.
2. At least one acceptance criterion is written as a Gherkin scenario (Given / When / Then) or an equivalent testable scenario.
3. **Hard gate:** every `done_when` item names a command, file artifact, metric, or user-observable behavior. Reject `done when "looks good"` style criteria.
4. Zero P0 open questions. Non-blocking assumptions are written with defaults and rationale.
5. The user has explicitly assented or supplied edits that you incorporated. Silence is not assent.
6. Contract audit: each acceptance criterion has a matching verification method; each constraint has a way to notice violation; no success criterion depends only on executor self-report.

## Hard upper bound: 8 user rounds

| Round | Behavior                                                                                  |
|-------|-------------------------------------------------------------------------------------------|
| 1–5   | Normal interview.                                                                         |
| 6     | Warn the user: "Two rounds left before I either write the contract or write a `blocked` brief." |
| 7     | Last chance to resolve P0 unknowns. Be explicit about what's still missing.               |
| 8     | Stop interviewing. Write either a complete contract or `blocked` with `blocking_unknowns` populated. |

Never pretend completion to dodge the cap. A `blocked` contract is a successful outcome — it tells the user exactly what new input is required before the contract can be considered complete.

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

## Anti-patterns to engineer out

See `references/anti-patterns.md` for the full failure-mode table with the prompt move that engineers each one out. The most important rules:

- **No yes/no until final approval.** Earlier questions must force a choice, rank, or edit.
- **No leading questions.** Always state your inference and evidence first, then ask the user to choose or correct it.
- **No faux confidence.** Maintain an explicit `open_questions` ledger in the draft artifact. You may not say "I understand" until the ledger is empty or remaining items are marked non-blocking with defaults.
- **No "are we good now?" loops.** One confirmation protocol at Phase 5, not repeated checks.
- **No anchoring on first phrasing.** Preserve `stated_request` and `underlying_goal` as separate fields. By round 2, restate at least two plausible interpretations.
- **No verification theater.** Every `done_when` needs concrete evidence — command, file artifact, metric, or user-visible behavior.
- **No runaway scope.** Default new ideas to "Could" or "Won't this time" (MoSCoW) unless the user explicitly promotes them.
- **No execution.** Never plan, write code, edit other files, or invoke other skills. The skill writes `GOAL.md` and stops. The user takes it from there.

## Resumption

If a goal artifact already exists in the working directory — `GOAL.md`, or `.claude/goals/<id>.checklist.json` / `.plan.md`:

1. Read it.
2. If `status: ready` (or, for a checklist, all required header fields are filled), the artifact is complete. Tell the user where it is and stop. Do not re-interview.
3. If `status: draft` or `blocked` (or a checklist whose `items`/header is incomplete), identify which fields are blank or in `blocking_unknowns`. Resume the interview by asking only for those fields. Do not re-ask filled fields. Increment `rounds_used` from where it left off.

## What this skill must not do

- Do not plan, write code, run the goal, or invoke another skill — ever. The deliverable is the artifact (contract, checklist, or phased doc) only. Execution belongs to goal-drive; hand the artifact off, but do not invoke goal-drive or run the work yourself.
- Do not infer the user's goal silently and proceed.
- Do not pretend completion at the round ceiling — write `blocked` instead.
- Do not relay to Codex or GPT-Pro during the interview unless the user explicitly asks for an external second opinion.
- Do not over-question Clear-domain tasks. Fast-lane them.

## Files in this skill

- `SKILL.md` — this file.
- `references/contract-template.md` — the `GOAL.md` skeleton with all required frontmatter and body sections (+ the optional `execution:` block for goal-drive).
- `references/checklist-template.md` — the JSON checklist artifact (enumerable / batched work).
- `references/phased-doc-template.md` — the phased design-doc artifact (staged work with per-phase acceptance).
- `references/cynefin-triage.md` — Phase 0 decision tree with worked examples.
- `references/question-bank.md` — worked questions per taxonomy category.
- `references/anti-patterns.md` — failure-mode table with the prompt move that engineers each one out.
- `references/goal-guardrail.md` — the optional Phase 5 `/goal` guardrail: condition template, per-shape derivation, and caveats (Claude Code only).

Read the references when you need them — not all up front. Long-form material is there so the model loads it only when relevant.
