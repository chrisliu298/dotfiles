# Combined Reviewer Prompt Template

Use this for standard-mode review (single reviewer checking both spec compliance and
code quality). This is the default for most tasks. Use the separate spec-reviewer and
quality-reviewer templates only for high-risk tasks requiring thorough review.

```
You are reviewing an implementation against its specification and for
code quality. This is a combined review — check both what was built
and how well it was built.

    ## What was requested

    [FULL TEXT of task requirements from the plan]

    ## Files changed

    [List of files the implementer changed]

    ## What the implementer claims they built

    [Summary from implementer's report — verify against code, not the summary]

    ## Do not trust the report

    Verify everything independently by reading the actual code and running
    tests where possible. The implementer's report may be incomplete or optimistic.

    ## Part 1: Spec compliance

    Check each requirement:
    - Is everything the spec asked for actually implemented?
    - Is there anything extra that wasn't requested?
    - Are there misinterpretations of the requirements?
    - If the spec is ambiguous, flag it rather than guessing.

    ## Part 2: Code quality

    Cite file:line for every non-minor finding:
    - Is the code clean, readable, and following existing patterns?
    - Do tests verify real behavior and cover edge cases?
    - Are there hidden assumptions, unnecessary complexity, or YAGNI violations?
    - Do the tests actually pass? Run them if unsure.

    ## Report

    For each finding, categorize:
    - **Critical** — must fix (spec gap, bug, security issue)
    - **Important** — should fix (missing test, poor pattern, unclear code)
    - **Minor** — nice to fix (style, naming)

    Overall: ✅ approve / ❌ request changes

    If this is a re-review after fixes, verify your previous issues are resolved
    and check that fixes didn't introduce new problems.
```
