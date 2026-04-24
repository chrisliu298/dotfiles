# AGENTS.md

## Working Principles

### Planning & Problem-Solving

- **Plan and review**: For multi-step tasks, state a plan with verification steps (`[Step] → verify: [check]`); use `update_plan` for substantial tasks. Re-plan when assumptions break.
- **One-shot delivery**: Ship features and bug fixes as one complete change—no "Phase 1/Phase 2", "Priority 1/Priority 2", or mid-task approval checkpoints. Plan internally in steps if needed (including with `update_plan`), but deliver one reviewable diff; do not use `update_plan` to serialize a single feature into sequential sub-deliverables. Phasing is only for genuinely large/risky work (multi-PR migrations, cross-cutting refactors)—state the reason before splitting.
- **Self-improvement**: After meaningful corrections, add a concise rule in AGENTS.md to prevent recurrence.
- **Debugging**: Create a minimal reproduction before fixing.
- **Browser auth debugging**: When persistent browser login fails, compare actual Chrome launch flags; profile path alone is insufficient if keychain/password-store flags differ.
- **Elegant solutions**: After a suboptimal fix, reconsider with full context—discard and implement a cleaner approach.
- **First-principles thinking**: Don't blindly follow the stated path—question whether the request is an XY problem. If the goal is unclear, stop and clarify before proceeding. If the goal is clear but the path is suboptimal, proactively suggest a simpler, lower-cost approach.
- **Test-driven development**: Write a failing test before production code. Watch it fail (setup errors don't count as RED). Write minimum code to pass. Refactor while green. One test, one behavior. Never skip verify-RED—a test you never saw fail could be testing the wrong thing.

### Code

- **Skimmable code**: Write extremely easy to consume code. Optimize for how easy the code is to read—make it skimmable, avoid cleverness, use early returns.
- **Minimal changes**: No TYPE_CHECKING imports, unnecessary abstractions, or scope expansion. Prefer simple imports. No large dependencies for small features. Don't refactor or reformat outside the task. When in doubt, do less.
- **Match existing style**: Conform to surrounding code's conventions (quotes, spacing, naming), even if you'd do it differently. Actively match, unless the task explicitly requires a different convention.
- **Surgical cleanup**: Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code—mention it, don't delete it.
- **Simplicity test**: If you write 200 lines and it could be 50, rewrite it. Would a senior engineer say this is overcomplicated? If yes, simplify.
- **Don't regenerate**: Use `curl`/`wget` for remote content. Never manually recreate.

### Agent Coordination

- **Concurrent subagents**: Use subagents for parallelizable or isolated work—no keyword trigger required. Spawn them asynchronously, continue local work while they run, and wait only when blocked or before final synthesis.
- **Self-review**: For non-trivial changes, run independent subagent reviews. Use 2 reviewers for risky/broad changes. Skip for trivial edits.
- **Redundancy vs. division**: Use redundant reviewers for diverse judgment on one question. Use parallel subtasks for naturally partitioned work. Don't conflate them.

## Python Environment

**NEVER use system Python. Always use a virtual environment.**

1. **Pick a venv**: Project `.venv/` if inside a project, otherwise global `~/.venv/`.
2. **Create if missing**: `uv venv` (project) or `uv venv ~/.venv` (global).
3. **Activate**: `source .venv/bin/activate` or `source ~/.venv/bin/activate`.
4. **Run**: Use the venv's `python`, `uv run`, or activated shell.

Use `uv add` or `uv sync` for packages (never `uv pip install` or system pip).
