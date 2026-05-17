# AGENTS.md

## Working Principles

### Planning & Problem-Solving

- **Plan and review**: For multi-step tasks, state a plan with verification steps (`[Step] → verify: [check]`); re-plan when assumptions break.
- **Task tracking**: For non-trivial work, keep a compact checklist tied to verification, update it as facts change, and reconcile it before finishing.
- **One-shot delivery**: Ship features and bug fixes as one complete change—no "Phase 1/Phase 2", "Priority 1/Priority 2", or mid-task approval checkpoints. Plan internally in steps if needed, but deliver one reviewable diff. Phasing is only for genuinely large/risky work (multi-PR migrations, cross-cutting refactors)—state the reason before splitting.
- **Self-improvement**: After meaningful corrections, propose a concise rule for AGENTS.md—only add if broadly reusable, to keep the file from bloating.
- **Debugging**: Create a minimal reproduction before fixing.
- **Minimum vs. ideal**: For non-trivial changes where the smallest patch and the cleanest structural fix diverge meaningfully, briefly state both options (1–2 lines each), recommend one, and proceed—only block on user input when the tradeoff is large enough to warrant it.
- **First-principles thinking**: Don't blindly follow the stated path—question whether the request is an XY problem. If the goal is unclear, stop and clarify before proceeding. If the goal is clear but the path is suboptimal, proactively suggest a simpler, lower-cost approach.
- **Context discipline**: Keep progress narration terse and useful. Summarize large logs, file dumps, and generated artifacts instead of pasting them into the conversation unless exact text is needed.
- **Test-driven development**: For behavior changes, prefer RED/GREEN/REFACTOR when practical—write a failing test, watch it fail (setup errors don't count as RED), make it pass, refactor while green. Skip for config, docs, mechanical migrations, or emergency fixes; explain when skipped.
- **Measure before optimizing**: For "did this make it better?" claims (agent quality, prompt changes, perf+accuracy tradeoffs), build the evaluation harness before iterating. Distinct from TDD: that's correctness, this is regression detection on fuzzy outputs. Without a number, every "improvement" is just changing posture.
- **Stop-the-line for missing infra**: When you hit a regression you can't bisect or a "did this help?" you can't answer, halt feature work and build the harness/CI first. The cost of not having it compounds faster than the cost of building it.

### Code

- **Minimal changes**: No TYPE_CHECKING imports, unnecessary abstractions, or scope expansion. Prefer simple imports. No large dependencies for small features. Don't refactor or reformat outside the task. Three similar lines beats a premature abstraction. When in doubt, do less.
- **Surgical cleanup**: Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code—mention it, don't delete it.
- **Don't regenerate**: Use `curl`/`wget` for remote content. Never manually recreate.
- **Workspace hygiene**: Keep scratch files out of the repo unless they are deliverables; use `/tmp` for experiments, delete temporary outputs before handoff, and do not add dead files, folders, or unused generated artifacts.

### Agent Coordination

- **Concurrent subagents**: Use subagents for parallelizable or isolated work—no keyword trigger required. Spawn them asynchronously, continue local work while they run, and wait only when blocked or before final synthesis.
- **Orchestrator role**: When coordinating agents, write bounded tasks with clear ownership and expected output. The lead agent remains responsible for synthesis, reviewing agent results, resolving conflicts, and deciding the final change.
- **Self-review**: For non-trivial changes, run independent subagent reviews. Use 2 reviewers for risky/broad changes. Skip for trivial edits.
- **Redundancy vs. division**: Use redundant reviewers for diverse judgment on one question. Use parallel subtasks for naturally partitioned work. Don't conflate them.

## Python Environment

**NEVER use system Python. Always use a virtual environment.**

1. **Pick a venv**: Project `.venv/` if inside a project, otherwise global `~/.venv/`.
2. **Create if missing**: `uv venv` (project) or `uv venv ~/.venv` (global).
3. **Activate**: `source .venv/bin/activate` or `source ~/.venv/bin/activate`.
4. **Run**: Use the venv's `python`, `uv run`, or activated shell.

Use `uv add` or `uv sync` for packages (never `uv pip install` or system pip).
