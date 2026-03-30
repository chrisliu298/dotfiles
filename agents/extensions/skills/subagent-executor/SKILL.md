---
description: |
  Execute a multi-task implementation plan by dispatching fresh subagents per task
  with review gates. Use when the user has multiple mostly-independent tasks and
  says "execute the plan", "implement these tasks", "dispatch subagents", "run
  through the plan", or invokes "subagent-executor". Also trigger when the user
  explicitly asks to start building after a plan was created. Best for tasks
  with disjoint write scopes that can be specified independently. Do NOT use for
  single-task work, tightly-coupled changes, or when the user wants to review
  each task manually.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
effort: max
---

# Subagent Executor

Execute an implementation plan by dispatching a fresh subagent per task. Each task gets an isolated implementer with exactly the context it needs, followed by review before moving on.

The value of fresh subagents is **context isolation**. An implementer carrying accumulated conversation history from previous tasks makes worse decisions — it conflates context, carries forward mistakes, and drifts from the plan. A fresh subagent with curated context stays focused.

## The process

### 1. Prepare

Read the plan once. For each task, determine:
- **Full description and acceptance criteria** — extract from the plan
- **Owned files/modules** — which files this task is allowed to create or modify
- **Dependencies** — does this task depend on output from another task?

Ensure you're on a feature branch, not a protected branch. Create one if needed.

### 2. Classify tasks

Before dispatching, decide the execution strategy:

- **Parallel-safe**: tasks with disjoint file ownership and no dependencies on each other. Dispatch these concurrently.
- **Sequential**: tasks that share files, depend on each other's output, or modify overlapping code. Dispatch these one at a time.

Default to parallel for independent tasks — this aligns with the general principle of launching subagents concurrently for parallelizable work. Fall back to sequential when write scopes overlap.

### 3. Per-task cycle

For each task:

**a. Dispatch implementer** — Read `references/implementer-prompt.md` for the template. Provide:
- Full task text from the plan (paste it, don't make the subagent read the plan file)
- Owned files/modules (explicit scope boundary)
- Scene-setting context (what was completed before, decisions that affect this task)
- Working directory

**b. Handle the implementer's status:**

| Status | Action |
|--------|--------|
| **DONE** | Proceed to review |
| **DONE_WITH_CONCERNS** | Read concerns; if about correctness, address before review; if observational, note and proceed |
| **NEEDS_CONTEXT** | Provide the missing information and re-dispatch |
| **BLOCKED** | Provide more context, break the task smaller, or escalate to the user |

Never ignore BLOCKED or NEEDS_CONTEXT. If the implementer says it's stuck, something needs to change before retrying.

**c. Review** — choose review depth based on task risk:

- **Standard (default)**: one reviewer checks both spec compliance and code quality. Read `references/reviewer-prompt.md`. Sufficient for most tasks.
- **Thorough**: separate spec reviewer then quality reviewer. Use for high-risk tasks — new public APIs, security-sensitive code, complex integration logic. Read `references/spec-reviewer-prompt.md` then `references/quality-reviewer-prompt.md`.

If the reviewer finds issues, the implementer fixes them and the reviewer checks again. **Escalate to the user after 2 failed review cycles** rather than looping indefinitely — two rounds of fix-and-re-review without convergence usually means the task needs clarification or the approach is wrong.

**d. Update context for subsequent tasks** — if later tasks depend on this one, note what was built (new types, APIs, file locations) for inclusion in their prompts.

### 4. Integration check

After all tasks are complete, verify the pieces fit together:
- Do tasks integrate correctly — are shared types, imports, and interfaces consistent?
- Are there duplicate implementations across tasks?
- Does the full implementation match the original plan's intent, not just individual task specs?
- Run the full test suite if one exists.

For small plans (3-4 low-risk tasks), a quick manual check may suffice. For larger or riskier plans, dispatch a final reviewer or use `lbreview` on the combined diff.

## Gotchas

- **Skipping spec review and going straight to quality.** These answer different questions: "did you build the right thing?" vs "did you build it well?" Code can be beautifully written and completely wrong. Spec compliance first, always.
- **Parallel implementers on overlapping files.** Parallel dispatch is safe only when write scopes are disjoint. If two tasks touch the same file, they must run sequentially. Assign explicit file ownership before dispatch.
- **Providing too little context to implementers.** A subagent with insufficient context will guess wrong. Include the full task description, relevant architecture, decisions from earlier tasks, and the project's testing/style conventions.
- **Not re-reviewing after fixes.** When a reviewer finds issues and the implementer fixes them, the reviewer must verify again. "The implementer says it's fixed" is not verification.
- **Continuing past a blocked task that downstream tasks depend on.** If task 3 is blocked and task 4 depends on task 3's output, don't dispatch task 4 — resolve the blocker first or replan with the user.
- **Not updating context between tasks.** A "fresh" subagent starts without knowledge of previous tasks. When task N+1 depends on output from task N, explicitly include that context in the prompt.
- **Making subagents read the plan file.** Provide the full task text in the prompt instead. The subagent doesn't need the full plan — it needs its task with curated context.

## Reference files

Read each template before dispatching the corresponding subagent. Adapt to the specific task — the templates are starting points, not rigid forms.

- `references/implementer-prompt.md` — Prompt template for task implementers
- `references/reviewer-prompt.md` — Combined spec + quality review (standard mode)
- `references/spec-reviewer-prompt.md` — Spec compliance only (thorough mode)
- `references/quality-reviewer-prompt.md` — Code quality only (thorough mode, after spec passes)
