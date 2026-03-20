# AGENTS.md

## Working Principles

### Planning & Problem-Solving

- **Plan and review**: For multi-step tasks, maintain a plan with `update_plan`; re-plan when assumptions break.
- **Self-improvement**: After meaningful corrections, add a concise rule in AGENTS.md to prevent recurrence.
- **Debugging**: Create a minimal reproduction before fixing.
- **Elegant solutions**: After a suboptimal fix, reconsider with full context—discard and implement a cleaner approach.
- **First-principles thinking**: Don't blindly follow the stated path—question whether the request is an XY problem. If the goal is unclear, stop and clarify before proceeding. If the goal is clear but the path is suboptimal, proactively suggest a simpler, lower-cost approach.

### Code

- **Skimmable code**: Write extremely easy to consume code. Optimize for how easy the code is to read—make it skimmable, avoid cleverness, use early returns.
- **Minimal changes**: No TYPE_CHECKING imports, unnecessary abstractions, or scope expansion. Prefer simple imports. No large dependencies for small features. Don't refactor or reformat outside the task. When in doubt, do less.
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
