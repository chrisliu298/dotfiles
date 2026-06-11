# GOAL.md template

The Goal Contract is a single Markdown file with YAML frontmatter. Path: `GOAL.md` at the repo root, or `$PWD` if not in a git repo. If the user wants to track multiple goals at once, write to `.claude/goals/<YYYYMMDD-HHMM>-<slug>.goal.md` instead and tell them.

## Frontmatter (required)

```yaml
---
schema_version: goal-contract/v1
id: 20260503-2200-api-timeout-fix      # YYYYMMDD-HHMM-<slug>; slug ≤ 30 chars, kebab-case
status: ready                           # ready | blocked | draft
cynefin_domain: complicated             # clear | complicated | complex
created_by: goal-elicit
created_at: 2026-05-03T22:00:00Z        # ISO 8601 UTC
approved_by_user: true
rounds_used: 4
blocking_unknowns: []                   # populated when status: blocked
source_prompt_summary: "User asked to clarify what they wanted before building X"
---
```

### Field rules

- `id` — `<YYYYMMDD>-<HHMM>-<slug>`. Generate with `date -u +%Y%m%d-%H%M`. Slug is a short kebab-case summary (≤ 30 chars).
- `status` — exactly one of three values. No "in_progress", no "almost_done".
- `cynefin_domain` — set in Phase 0; do not revise downward (don't claim "clear" after asking 4 rounds).
- `approved_by_user` — `true` only after the user explicitly said "approved", "yes use this", or supplied edits that you incorporated. Silence is not assent.
- `rounds_used` — number of user turns consumed by the interview, including resumed turns.
- `blocking_unknowns` — empty list if `status: ready`. Non-empty list of P0 questions when `status: blocked`.

### Optional: execution block (for goal-drive)

A contract is handed off and the skill stops. If the user wants it later **driven to done** by
goal-drive, add an optional `execution:` block to the frontmatter (absent ⇒ elicit-only,
the default — today's behavior). Full semantics: the goal-drive skill's
`references/artifact-formats.md`.

```yaml
execution:
  work_shape: one_shot          # contracts are ALWAYS one_shot
  commit_policy: none           # none | per_unit — per_unit AUTHORIZES a local commit per verified unit, no asking
  authority:
    allow_paths: ["src/**"]
    allow_commands: ["pytest"]
    stop_for: [deploy, db_migration, destructive, protected_branch_push, secrets, network_send]
```

This block is **one_shot only**. For enumerable or staged work, write the dedicated artifact
instead (`checklist-template.md` / `phased-doc-template.md`) — **not** a companion `GOAL.md`.
One goal, one artifact.

## Body (required sections, in this order)

```markdown
# Goal Contract — <id>

## Stated request
<Verbatim seed prompt from the user. Do not paraphrase.>

## Underlying goal
<What the user is actually trying to achieve. May be the same as Stated request
for clear-domain tasks; usually different after an XY check.>

## Job-to-be-done
When <situation>, I want <capability or change>, so I can <outcome>.

## Objective
<One sentence, deliverable-oriented. Avoid vague verbs like "improve" unless
paired with measurable behavior.>

## Stakeholders / decision owner
- Decision owner: <who accepts the result>
- Affected: <who feels the change>
- Excluded: <who is explicitly out of scope>

## Scope in
- <Bullet 1>
- <Bullet 2>

## Scope out / non-goals
- <Tempting adjacent work that must NOT be done>

## Guidance (optional — for open-ended or ambitious goals; omit for Clear-domain tasks)
- Starting point: <where to begin — a file, module, command, or hypothesis to try first; a hint, not a lock>
- Avoid: <approaches or paths already known to be dead ends>
- Reference: <path to an existing plan/research/profile the executor should read first, rather than rediscover>

## Constraints
- Stack: <languages, frameworks, versions>
- Style: <linting, formatting, conventions to match>
- Policy: <security, privacy, compliance>
- Time: <deadline or budget>
- Dependencies: <what must be available; what must not be added>
- Compatibility: <existing callers, schemas, APIs to preserve>

## Assumptions
- <Non-blocking assumption>: <default chosen, rationale>

## Open questions
- (P0 = blocking; P1 = should resolve; P2 = nice-to-resolve)
- P0: <question> — <why it blocks>     # only present when status: blocked
- P1: <question>
- P2: <question>

## Acceptance criteria

### Scenario 1: <name>
Given <precondition>
When <action>
Then <observable outcome>

### Scenario 2: <name>
Given …
When …
Then …

## Done when
- [ ] <criterion 1> → <command | file artifact | metric | user-visible behavior>
- [ ] <criterion 2> → <evidence>
- [ ] <criterion 3> → <evidence>

## Verification plan
- <Command to run, expected output>
- <Manual check, what to look for>
- <Test file to run, which tests must pass>

## Observability / evidence
- <Where evidence will appear: log path, UI page, file diff, metric dashboard>
- <Optional, for ambitious/multi-step goals: the progress signal to re-check during the work — a metric trend or done-count — not only the final proof>

## Risks and mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| <description> | low/med/high | low/med/high | <mitigation> |

## Rollback plan
<How to undo, disable, or contain the change. Specific commands or steps.>

## Final response contract
<What the executing agent must report when done. Include: which Done When items
were verified with what evidence, what was deferred to a follow-up contract, any
new risks discovered.>
```

## Example: minimal complete contract

```markdown
---
schema_version: goal-contract/v1
id: 20260503-2200-rename-foo
status: ready
cynefin_domain: clear
created_by: goal-elicit
created_at: 2026-05-03T22:00:00Z
approved_by_user: true
rounds_used: 1
blocking_unknowns: []
source_prompt_summary: "Rename variable foo → user_id in src/auth.py"
---

# Goal Contract — 20260503-2200-rename-foo

## Stated request
Rename the variable foo to user_id in src/auth.py.

## Underlying goal
Same as stated.

## Job-to-be-done
When reading auth.py, I want the variable name to reflect what it holds, so
I can understand the code without context.

## Objective
Rename `foo` to `user_id` in `src/auth.py` and update every reference in-repo.

## Stakeholders / decision owner
- Decision owner: user
- Affected: anyone touching auth.py
- Excluded: external API consumers (the variable is internal)

## Scope in
- Rename `foo` → `user_id` in `src/auth.py`
- Update all in-repo references via `rg` + edit

## Scope out / non-goals
- Refactoring auth.py beyond this rename
- Touching tests unless they reference `foo`

## Constraints
- Style: match existing snake_case convention
- Policy: no behavior change

## Assumptions
- The name `user_id` is not already taken in the same scope (verify before edit)

## Open questions
(none)

## Acceptance criteria

### Scenario 1: rename complete
Given the working tree
When I `rg '\bfoo\b' src/`
Then no matches remain

## Done when
- [ ] `rg '\bfoo\b' src/` returns no matches → command output
- [ ] `pytest tests/test_auth.py` passes → test command
- [ ] `git diff` shows only renames, no logic changes → diff inspection

## Verification plan
- `rg '\bfoo\b' src/` (must be empty)
- `pytest tests/test_auth.py`
- `git diff src/auth.py | grep -E '^[-+]' | grep -v 'foo\|user_id'` (must be empty)

## Observability / evidence
- File diff in `git diff src/auth.py`
- Test runner output

## Risks and mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Other modules import `foo` from auth.py | low | med | grep all imports before edit |

## Rollback plan
`git restore src/auth.py` and any other file touched.

## Final response contract
Report: files touched (count + names), `rg` output (empty), test result (pass/fail).
```
