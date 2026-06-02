# Question bank

Worked examples for each taxonomy category, phrased to **force a decision** rather than invite a yes/no. Adapt the wording to the user's seed request — these are starting templates, not a checklist.

The structure for every good elicitation question:
1. State your inference and the evidence behind it (when applicable).
2. Ask the user to choose, rank, edit, or supply concrete information.
3. Avoid yes/no until the final approval in Phase 5.

## 0. Work shape (asked once, during triage/converge — sets which artifact)

- "Is this (a) one task with a few steps, (b) a list of similar items to grind through, or (c) a staged build where later steps depend on earlier ones? (a) → a single contract, (b) → a checklist the executor batches, (c) → a phased plan with per-phase acceptance."
- "Could a script enumerate the units of work (files, symbols, endpoints)? If yes, I'll write a checklist and you (or your script) can fill the item list."
- "Should commits happen as it runs? Default is no auto-commit; opt in and the executor makes one local commit per verified batch/phase (it never pushes — that stays your call)."

## 1. Intent

- "What outcome would make you say this was worth the effort? Try to name something a third party could observe."
- "What's the smallest result that would still be a win? What's the largest result that would still feel reasonable?"
- "If I could deliver only one of (a) the thing you asked for or (b) the underlying thing, which?"
- "What were you doing right before you decided this needed to happen?"

## 2. XY check

- "What made you pick this approach in particular? Was there a path you considered first?"
- "Pretend the approach you described didn't exist. How would you describe what you need?"
- "Is there an existing way to get this outcome that you've ruled out? Why?"
- "What would a workaround look like if I couldn't do this the way you described?"

## 3. Job-to-be-done

- "Fill in: when [...], I want [...], so I can [...]."
- "What's the situation that triggers needing this? Once a day? Once a quarter? Only when X happens?"
- "Who feels the pain when this isn't done?"
- "Once this exists, what's the next thing you'd want?"

## 4. Stakeholders / decision owner

- "Who needs to sign off before this is considered done — you, a team, a user, a CI gate?"
- "Who *uses* the result, and who is affected by its failure?"
- "Is there anyone whose objection would override yours on this?"
- "Should I treat you as the only acceptance authority, or do you want me to write the contract so a teammate could check the work?"

## 5. Scope in

- "Pick one: I should do (a) only the central thing you mentioned, (b) the central thing plus the obvious adjacent fixes, (c) the central thing plus the larger refactor it suggests."
- "List the files/modules I'm allowed to touch. I'll treat anything else as out of scope."
- "What's the smallest version of this that would still be useful?"

## 6. Scope out / anti-goals

- "What looks adjacent and tempting but I should *not* do, even if it would seem like a good time?"
- "Is there code that I should treat as 'do not touch' even if it's clearly bad?"
- "What change to user-visible behavior would be unacceptable?"
- "Are there any files, branches, or environments I should never write to during this work?"

## 7. Constraints

- "What stack / language / framework / version constraints apply?"
- "Any style or convention I should match? Point me at a file that's the gold standard if you can."
- "Is adding new dependencies allowed? If yes, are any classes of dep off-limits (LGPL, native deps, ...)?"
- "What's the time/budget envelope — minutes, an afternoon, multi-day?"
- "Any compatibility constraints — public API, schema versions, on-disk file formats, downstream consumers?"
- "Security / privacy / compliance constraints?"

## 8. Prior attempts and current state

- "Has anyone tried this before, here or elsewhere? What stopped them?"
- "What's the current state of the thing you want to change? Working but ugly? Half-broken? Greenfield?"
- "Are there branches, draft PRs, or scratch files I should look at before I start?"
- "What context should I *not* spend time rediscovering — what do you already know is true?"

## 9. Success criteria

- "What observable facts would prove this is done? Name commands, files, or behavior I can check."
- "What would make you reject the result even if everything else worked?"
- "If we ran this 100 times, what fraction has to succeed?"
- "What's the minimum amount of evidence I should report when I claim success?"

## 10. Definition of done

- "Is 'tests pass' enough, or does the work need to be deployed / merged / in production / observed under load?"
- "Does done include documentation, a CHANGELOG entry, a migration guide, a notice to users?"
- "What's the cleanup criterion — temporary debugging code removed, feature flags wired, dead code deleted?"

## 11. Risks and edge cases

- "What's the most expensive way this could go wrong?"
- "What inputs / states would make a naive implementation produce a wrong result?"
- "Is there a known failure mode from prior work in this area?"
- "What concurrent or boundary condition could break this — high load, empty input, very large input, network failure, partial writes?"

## 12. Rollback / containment

- "If this turns out to be wrong in production, what's the fastest way to undo it?"
- "Can it be guarded by a feature flag? Should it be?"
- "Is there a soft-launch path — dark launch, canary, opt-in flag?"
- "What state changes are *not* easily reversible (data migrations, external API calls, sent messages)?"

## 13. Observability

- "Where will evidence appear when this works — logs, metrics, UI, file diff, test output, user reports?"
- "What signal would tell you it's *not* working — error rate, latency spike, user complaint, missing log line?"
- "Is there an existing dashboard or alert I should reuse, or do we need to add one?"

## 14. Deadline / sequencing

- "Real deadline (something happens / breaks if we miss) or aspirational?"
- "What's blocked on this? What does this block?"
- "Is there a hard order — does X have to ship before Y?"

## Pattern: forcing a decision instead of asking yes/no

Bad:
> "Should I cache only GET requests?"

Good:
> "Cache scope: (a) GET only, (b) GET + idempotent POSTs, (c) every read-heavy endpoint regardless of method. (a) is safest, (c) is highest leverage, (b) is the middle. Which?"

Bad:
> "Do you want tests?"

Good:
> "Tests: (a) one Gherkin scenario for the happy path, (b) Gherkin happy + 1–2 error cases, (c) full unit coverage of the new function plus integration test. Pick one."

## Pattern: stating an inference before asking

Bad:
> "What's the underlying goal?"

Good:
> "I infer the underlying goal is to reduce signup-funnel drop-off, because you mentioned the conversion dashboard. The plausible alternative is that you want to add an A/B test infrastructure that happens to be wired to signup. Which is right?"
