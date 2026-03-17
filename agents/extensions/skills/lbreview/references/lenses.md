# Reviewer Lenses

Three adversarial perspectives to stress-test a change. Apply based on diff size.

## Skeptic

Challenge correctness and completeness:

- What inputs, states, or sequences will break this?
- What error paths are unhandled or silently swallowed?
- What race conditions or ordering dependencies exist?
- What does the author believe is true that isn't proven?

## Architect

Challenge structural fitness:

- Does the design actually serve the stated goal, or a goal the author assumed?
- Where are the coupling points that will hurt when requirements shift?
- What boundary violations exist? Where does responsibility leak between components?
- What implicit assumptions about scale, concurrency, or ordering will break first?

## Minimalist

Challenge necessity and complexity:

- What can be deleted without losing the stated goal?
- Where is the author solving problems they don't have yet?
- What abstractions exist for a single call site?
- Where is configuration or flexibility added without a concrete second use case?
- Is this the simplest path to the outcome, or the path that felt most thorough?
