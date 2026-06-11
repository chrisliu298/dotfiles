# Anti-patterns

Failure modes that elicitation skills fall into, with the concrete prompt move that engineers each one out. Read this when designing or auditing the interview behavior.

| Failure mode                 | What happens                                                   | Mitigation                                                                                              |
|------------------------------|----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| Over-questioning             | Skill interrogates trivial tasks, becomes a tax on simple work.| Phase 0 Cynefin triage. Clear-domain tasks get fast lane (1 confirmation, no full interview).           |
| Under-questioning            | Skill acts on ambiguity to avoid friction.                     | Stop criteria block `ready` while any P0 field is missing. Hard cap at round 8 forces resolution or `blocked`. |
| Faux Socratic loops          | Questions sound thoughtful but don't reduce uncertainty.       | Every question must name the contract field it resolves. The running summary lists *which* unresolved fields are next. |
| Leading questions            | Skill steers user toward its preferred solution.               | Always state your inference and the evidence behind it: "I infer X because Y; alternatives are A and B; which is right?" |
| Yes/no theater               | User says yes without inspecting meaning.                      | No yes/no until Phase 5 final approval. Earlier questions force a choice, rank, or edit.                |
| Faux confidence              | Skill claims understanding while material things are unknown.  | Maintain explicit `open_questions` ledger in draft GOAL.md. Cannot say "I understand" until ledger is empty or remaining items marked non-blocking. |
| "Are we good now?" loops     | Skill asks for re-approval after every revision.               | One confirmation protocol at Phase 5: "I will write this as the contract unless you change one of these fields: [list]." Not "is this OK now?" |
| Anchoring on first phrasing  | Skill treats the requested implementation as the goal.         | Always preserve `stated_request` and `underlying_goal` as separate fields. By round 2, restate at least two plausible interpretations. |
| Framing effects              | Early wording narrows the solution space prematurely.          | The two-interpretation restate at round 2 forces re-framing. Diverge phase actively widens the frame.   |
| Sunk-cost in early questions | Bad early assumptions persist through later rounds.            | Running summary every 2 rounds includes "changed or discarded assumptions" as an explicit section.      |
| Premature commitment         | Skill starts planning, coding, or invoking other skills.       | Hard rule in SKILL.md: do not plan, code, edit other files, run the goal, or invoke other skills — ever. The skill writes the artifact (contract, checklist, or phased doc) and stops. Execution is the separate goal-drive skill; goal-elicit hands off the artifact but never invokes goal-drive. |
| Premature convergence        | Skill writes contract at round 2 to seem efficient.            | Stop criteria must all be true. Require at least one Gherkin scenario and at least one anti-goal for non-Clear tasks. |
| Verification theater         | "Done" is a vibes check.                                       | Hard gate: every `done_when` item must name a command, file artifact, metric, or user-observable behavior. Reject "looks good", "works well", "feels right". |
| Proxy-signal completion      | Tests pass but the actual user need isn't met.                 | Contract audit (stop criterion 6): each acceptance criterion must have a *direct* verification — not "the test suite passes" as a stand-in. |
| Gamed criterion              | A threshold/metric `done_when` is met by degrading the real goal — cut coverage to hit "100% pass", crop/inline a reference image to look "pixel-perfect", lower a budget instead of meeting it. | For each threshold or metric criterion, name the cheap wrong way to satisfy it and add a guard criterion (a coverage floor, a no-crop check, an unchanged-budget assertion). Pairs with goal-drive's "never weaken the verifier" rule. |
| Visual rabbit-hole           | A screenshot/mockup becomes the acceptance criterion; the executor fixates on pixel-level fidelity (icons, spacing) and burns effort while missing functional correctness. | Treat images as *context*, not acceptance. Derive `done_when` from a feature checklist, spec, or design-system/token conformance — never "matches this image" as the sole criterion. Put the reference under Observability/context, not in `done_when`. |
| Hidden stakeholder mismatch  | Skill satisfies the requester's wording but not the accepter's needs. | `Stakeholders / decision owner` is a required section. Acceptance authority must be named.       |
| Risk blindness               | Skill ignores rollback, deadlines, production impact.          | `Risks`, `Rollback`, `Observability` are required sections for non-Clear tasks. Question taxonomy mandates these.|
| Runaway scope                | Interview keeps adding to the task.                            | Default any new idea introduced after round 2 to "Could" or "Won't this time" (MoSCoW) unless user explicitly promotes it. Each promotion is a recorded decision. |
| User fatigue                 | Even good elicitation is exhausting at scale.                  | 3–5 questions per turn (2 if heavy). Running summary every 2 rounds. Hard cap at round 8.               |
| False completion at the cap  | Skill pretends `ready` to dodge the round limit.               | At round 8, write either a complete contract *or* `blocked` with `blocking_unknowns` populated. Mid-flight assertion in SKILL.md. |
| Chatty wrap-up               | Skill summarizes at the end with no actionable artifact.       | The artifact *is* the deliverable. Tell the user where `GOAL.md` is and stop — no prose summary.        |
| Skill-on-skill recursion     | Skill calls /goal-elicit recursively or invokes other skills.  | Forbidden in SKILL.md. Only `Read`, `Write`, `Edit`, narrow `Bash`, and `AskUserQuestion` are allowed.  |

## Empirical reminder

Recent agentic-clarification work (SAGE, ClarifyCoder) shows the dual failure: agents *over-clarify* low-impact details and *under-clarify* critical missing information at the same time. The fix is not "ask more" or "ask less" — it's "ask only when the question maps to a missing contract field, and never act when a P0 field is empty".

This is why every question in this skill must be tied to a field in `references/contract-template.md`. If you can't say which field a question fills, don't ask it.

## Audit checklist

Before marking `status: ready`, verify:

- [ ] Every required frontmatter field is set.
- [ ] Every required body section exists and is substantive (not "TBD").
- [ ] At least one acceptance criterion is in Gherkin form.
- [ ] Every `done_when` line has an evidence source after the arrow.
- [ ] `open_questions` is empty OR every remaining item is marked non-blocking with a chosen default.
- [ ] `stakeholders` names at least one acceptance authority.
- [ ] `rollback` is concrete (specific commands or steps), not "revert if needed".
- [ ] `cynefin_domain` matches the actual interview shape (clear ≤ 1 round; complicated 3–5; complex 4–6 with probe contract).
- [ ] `approved_by_user: true` is set only after an explicit assent or incorporated edit.

If any check fails, do not write `ready`. Either continue the interview or write `blocked`.
