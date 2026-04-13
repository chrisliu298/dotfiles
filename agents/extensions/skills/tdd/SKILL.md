---
description: |
  Enforce test-driven development: write a failing test before any production code.
  Use when implementing new features or fixing bugs and the user says "TDD",
  "test first", "write tests first", "red green refactor", or invokes "tdd".
  Also consider triggering when the user asks to add new behavior or fix a bug
  in a module with existing test coverage. Do NOT use for throwaway prototypes,
  config changes, refactors with no behavior change, or when the user says
  "skip tests" or "no tests needed".
user-invocable: true
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
effort: high
---

# Test-Driven Development

Write the test first. Watch it fail. Write minimal code to pass. Refactor.

The value of TDD is not the tests themselves — it's the **failing step**. A test you never saw fail could be testing the wrong thing entirely. Watching it fail proves it tests what you think it tests.

## Before starting

Identify the test framework, runner command, and test file location pattern before writing anything. Check `package.json` scripts, `pyproject.toml`, `Cargo.toml`, `Makefile`, or CI config. Match the existing framework and style exactly — guessing the wrong test runner wastes a cycle and produces confusing failures.

If the project has no test suite, ask the user whether to set one up or skip TDD.

## The Cycle

### 1. RED — Write one failing test

Write the smallest test that describes the next behavior you need. One test, one behavior. If one test exercises multiple independent outcomes, split it.

```text
// Good: clear name, tests one real behavior
test('rejects empty email')
  result = validateEmail('')
  expect result.error == 'Email required'

// Bad: vague, tests mock not behavior
test('email works')
  mock = jest.fn().mockReturnValue(true)
  expect mock('') == true
```

### 2. Verify RED — Run it, confirm it fails

```bash
# Run the specific test file, not the full suite
npm test path/to/test.ts  # or pytest, cargo test, go test, etc.
```

Confirm:
- The test **fails** (not errors — a syntax error or import error is not a failing test)
- It fails because the feature is **missing**, not because of a typo or broken setup
- The failure message matches your expectation

If the test passes immediately, you're testing existing behavior. Rewrite the test.

### 3. GREEN — Write the minimum code to pass

Write the simplest implementation that makes the test green. No extras, no "while I'm here" improvements, no future-proofing.

### 4. Verify GREEN — Run it, confirm all tests pass

Run the test again. Confirm the new test passes and existing tests still pass. If unrelated tests are already failing, note them but don't let pre-existing failures block your cycle.

### 5. REFACTOR — Clean up while green

Remove duplication, improve names, extract helpers. Keep all tests passing. Don't add new behavior in this step.

### 6. Repeat

Next failing test for the next behavior.

## Already wrote code without tests?

Set it aside — don't extend it. Write a failing test first, then re-drive the implementation from the test. If the code is small and uncommitted, discard and rewrite from the test. If it's substantial, write characterization tests (tests that capture current behavior) first, then continue in TDD-sized increments. Ask the user if unsure.

The point: keeping pre-written code leads to tests that pass immediately, which proves nothing.

## When stuck

- **Test is hard to write.** The code under test probably has too many dependencies. Extract the logic into a pure function that's easy to test, or write a characterization test to establish a baseline first.
- **Test fails for the wrong reason.** Fix the test harness or setup before touching production code. A broken import is not RED — it's a setup problem.
- **No practical test entry point.** Pause and ask the user whether to invest in testability or skip TDD for this piece.

## Gotchas

These are the real failure points when doing TDD with an AI agent:

- **Skipping verify-RED.** The strongest instinct is to write the test, then immediately write the implementation without running the test first. The failing step is the whole point — run the test and read the failure output before writing any production code. Every time.
- **Counting a setup error as RED.** An import error, missing module, or syntax error is not a failing test. RED means the intended assertion fails for the intended reason — because the feature is missing.
- **Testing implementation details instead of behavior.** Tests coupled to private methods, internal state, or call counts break on every refactor and prove nothing about correctness. Assert on the observable behavior at the API boundary.
- **Writing tests that are too broad.** A test named "handles all validation" is not TDD — it's the whole feature spec as one test. One test, one behavior. Let each test drive one small increment.
- **Over-engineering in GREEN.** The GREEN step is "minimum code to pass," not "the final design." Future tests will drive the design forward. Resist adding parameters, options, or abstractions that no test requires yet.
- **Using mocks when real code is available.** Mocking hides real behavior. If the database is available, test against it. Only mock external services you can't control or that are prohibitively slow.
- **Refactoring while RED.** If tests are failing, get to GREEN first. Refactoring with a failing test means you're changing two things at once.

For bug fixes, use `diagnose` to establish the root cause first, then enter the TDD cycle: the failing test is your RED step, the fix is GREEN.
