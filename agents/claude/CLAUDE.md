# CLAUDE.md

## Working Principles

### Planning & Problem-Solving

- **Plan before implementing**: For complex or multi-step tasks, create and maintain a plan with your planning workflow. Re-plan when assumptions break. For simple tasks (documentation edits, single-file changes, small fixes), skip planning and execute directly.

- **Adversarial plan review**: For non-trivial plans (>3 steps, multi-file scope), use `/prism` to get independent multi-agent review before implementation. Skip for trivial plans.

- **Challenge and verify**: Surface assumptions, risks, and missing evidence. If multiple approaches exist, present the tradeoffs—don't pick silently. Verify behavior with focused checks and report concrete results.

- **Elegant solutions**: After a suboptimal fix, reconsider the approach. With full context available, discard the current solution and implement a cleaner one.

- **Autonomous problem-solving**: Fix bugs autonomously when given context—paste a Slack thread or error log and say "fix." Say "Go fix the failing CI tests" without specifying how. Use docker logs to troubleshoot distributed systems.

- **Self-improvement**: After meaningful corrections, add a concise rule in CLAUDE.md (or project notes) when it prevents a recurring mistake.

- **Debugging approach**: When debugging, create a minimal reproduction before attempting a fix. Explain the reasoning behind changes, not just the changes themselves.

### Code & Implementation

- **Minimal implementations and changes**: Keep code changes minimal. No TYPE_CHECKING imports, no unnecessary abstractions, no scope expansion beyond what was asked. Prefer simple, direct imports. Don't introduce large dependencies for small features. Avoid cleverness unless it clearly improves the outcome. Write code another strong engineer can quickly understand, safely extend, and confidently ship. If in doubt, do less.

- **Add regression tests**: When fixing a bug, add a test that reproduces the failure before applying the fix. This ensures the bug stays fixed and prevents silent regressions. Skip this for trivial fixes or projects without an existing test setup.

- **Match existing style**: When editing existing code, follow the surrounding conventions (naming, formatting, patterns) even if you'd do it differently. Don't refactor or reformat adjacent code that isn't part of the task.

- **Verify file paths first**: Before reading or editing files, verify actual file paths. Never assume file locations based on project conventions alone.

- **Use platform-native tools**: Prefer patch/edit tools for focused edits and shell commands for bulk operations. Avoid references to tools that are unavailable in the current agent.

- **Copy or move, don't regenerate**: When a file needs to be copied, moved, or duplicated, use `cp`, `mv`, or similar shell commands. Never regenerate a file's contents from scratch when it already exists and can be directly copied or moved. Even if the file needs modifications, copy/move it first, then edit it in place. Regenerating wastes tokens and risks introducing errors.

- **Commit only when asked**: Do not commit or push unless the user explicitly requests it.

### Agent Coordination

- **Use subagents intentionally**: Use subagents when work can be parallelized or cleanly isolated. No keyword trigger is required.

- **Concurrent execution**: Launch independent agents concurrently in the background (`run_in_background: true`). Always wait for ALL to return before synthesizing — partial results lose the value of slower but careful agents.

- **Self-review with subagents**: For non-trivial changes, run independent subagent reviews. Use 2 reviewers for risky or broad changes. Skip subagent review for trivial edits (typos, single-line changes, simple docs updates).

- **Redundancy vs. division of labor**: Use Prism (redundancy) when the task benefits from diverse judgment on the same question — reviews, decisions, analysis. Use parallel subagents with distinct tasks (division of labor) when the work is naturally partitioned into independent subtasks with different inputs/outputs. Do not force division-of-labor tasks into Prism, and do not force judgment tasks into parallel subtasks.

### Tooling & Workflow

- **Skills and automation**: If a task is performed more than once daily, suggest turning it into a skill or command. Examples: a `/techdebt` command to find and remove duplicated code at session end, or a command that aggregates recent Slack/docs/GitHub into one context dump.

- **Extensions live in `~/dotfiles/agents/extensions/`**: When creating or updating skills, always write to `~/dotfiles/agents/extensions/skills/<skill-name>/`. This is the canonical location; running `./dotfiles.sh` syncs them to `~/.claude/skills/` and `~/.codex/skills/` automatically.

- **Download, don't generate**: When installing files from URLs (skills, configs, etc.), use `curl`/`wget` to download directly. Avoid manually recreating remote file contents.

- **Data and analytics**: Use CLI tools (bq, psql, sqlite3, etc.) directly for data queries and analysis. Any database with a CLI, MCP, or API works. Users should not need to write SQL or switch contexts.

## Python Environment

**NEVER use system Python (`/opt/homebrew/bin/python3`, `/usr/bin/python3`, etc.). Always use a virtual environment.**

Before any Python operation:

1. **Pick a venv**: Use a project-level `.venv/` when inside a project directory. Otherwise, use the global `~/.venv/`.
2. **Create if missing**: `uv venv` (project) or `uv venv ~/.venv` (global).
3. **Activate**: `source .venv/bin/activate` or `source ~/.venv/bin/activate`.
4. **Run**: Use the venv's `python`, `uv run`, or activated shell.

Use `uv pip install` or `uv sync` for packages (never system pip).
