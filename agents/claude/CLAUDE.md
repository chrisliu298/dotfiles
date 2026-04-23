# CLAUDE.md

## Working Principles

### Planning & Problem-Solving

- **Plan and review**: For multi-step tasks, state a plan with verification steps (`[Step] → verify: [check]`); re-plan when assumptions break.
- **One-shot delivery**: Ship features and bug fixes as one complete change—no "Phase 1/Phase 2", "Priority 1/Priority 2", or mid-task approval checkpoints. Plan internally in steps if needed, but deliver one reviewable diff. Phasing is only for genuinely large/risky work (multi-PR migrations, cross-cutting refactors)—state the reason before splitting.
- **Self-improvement**: After meaningful corrections, add a concise rule in CLAUDE.md to prevent recurrence.
- **Debugging**: Create a minimal reproduction before fixing.
- **Elegant solutions**: After a suboptimal fix, reconsider with full context—discard and implement a cleaner approach.
- **First-principles thinking**: Don't blindly follow the stated path—question whether the request is an XY problem. If the goal is unclear, stop and clarify before proceeding. If the goal is clear but the path is suboptimal, proactively suggest a simpler, lower-cost approach.
- **Test-driven development**: Write a failing test before production code. Watch it fail (setup errors don't count as RED). Write minimum code to pass. Refactor while green. One test, one behavior. Never skip verify-RED—a test you never saw fail could be testing the wrong thing.

### Code

- **Skimmable code**: Write extremely easy to consume code. Optimize for how easy the code is to read—make it skimmable, avoid cleverness, use early returns.
- **Minimal changes**: No TYPE_CHECKING imports, unnecessary abstractions, or scope expansion. Prefer simple imports. No large dependencies for small features. Don't refactor or reformat outside the task. When in doubt, do less.
- **Match existing style**: Conform to surrounding code's conventions (quotes, spacing, naming), even if you'd do it differently. Actively match, don't just avoid changing.
- **Surgical cleanup**: Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code—mention it, don't delete it.
- **Simplicity test**: If you write 200 lines and it could be 50, rewrite it. Would a senior engineer say this is overcomplicated? If yes, simplify.
- **Don't regenerate**: Use `cp`/`mv` for existing files, `curl`/`wget` for remote content. Never recreate from scratch—copy/move first, then edit in place.

<important if="you are spawning or coordinating subagents">

### Agent Coordination

- **Concurrent subagents**: Use subagents for parallelizable or isolated work—no keyword trigger required. Launch in background (`run_in_background: true`). Wait for ALL before synthesizing.
- **Self-review**: For non-trivial changes, run independent subagent reviews. Use 2 reviewers for risky/broad changes. Skip for trivial edits.
- **Redundancy vs. division**: Use redundant reviewers for diverse judgment on one question. Use parallel subtasks for naturally partitioned work. Don't conflate them.

</important>

<important if="you are running Python, creating virtual environments, or installing packages">

## Python Environment

**NEVER use system Python. Always use a virtual environment.**

1. **Pick a venv**: Project `.venv/` if inside a project, otherwise global `~/.venv/`.
2. **Create if missing**: `uv venv` (project) or `uv venv ~/.venv` (global).
3. **Activate**: `source .venv/bin/activate` or `source ~/.venv/bin/activate`.
4. **Run**: Use the venv's `python`, `uv run`, or activated shell.

Use `uv add` or `uv sync` for packages (never `uv pip install` or system pip).

</important>
