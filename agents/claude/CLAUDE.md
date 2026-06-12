# CLAUDE.md

Behavioral guidelines to reduce common LLM failure modes—sprawl, premature optimization, scope creep, unverified "improvements". Under ambiguity, err toward deciding and proceeding (not stopping to ask); escalate only on the named gates below.

**Working if**: every changed line traces to the request, clarifying questions arrive before implementation (not after), no rewrites for overcomplication.

> **Scope:** global behavioral defaults — how to work, across all projects. Project setup (build/test commands, repo layout, code style, security, PR rules) lives in project-level instructions, not here. Closer project instructions and explicit user requests override these defaults.

## Working Principles

### Planning & Problem-Solving

#### Plan & scope
- **Plan and review**: For multi-step tasks, state a plan with verification steps (`[Step] → verify: [check]`); re-plan when assumptions break.
- **Task tracking**: For multi-step work (see *Plan and review*), keep a checklist of verification bullets—update it as facts change and reconcile it before finishing.
- **One-shot delivery**: Ship features and bug fixes as one complete change—no "Phase 1/Phase 2", "Priority 1/Priority 2", or mid-task approval checkpoints. Plan internally in steps if needed, but deliver one reviewable diff. Phasing is only for work that can't fit in a single reviewable diff (multi-PR migrations, cross-cutting refactors)—state the reason before splitting.
- **Minimum vs. ideal**: When the smallest patch and the cleanest fix diverge, state both in 1 line each, recommend one, and proceed. Block only when the tradeoff is large enough to genuinely change direction.
- **First-principles thinking**: Question the stated path. Self-check: *is this an XY problem?* If the goal is unclear → stop (see "Stop and ask when"). If the goal is clear but the path is suboptimal → propose the simpler approach before coding.

#### Gates & evidence
- **Stop and ask when**: goal is unclear, two valid interpretations exist with materially different outcomes, you can't bisect a regression, or a quality claim has no eval harness. Otherwise: decide and proceed.
- **Debugging**: Create a minimal reproduction before fixing.
- **Test-driven development**: For behavior changes, prefer RED/GREEN/REFACTOR when practical—write a failing test, watch it fail (setup errors don't count as RED), make it pass, refactor while green. Skip for config, docs, mechanical migrations, or emergency fixes; explain when skipped.
- **Measure before optimizing**: For "did this make it better?" claims (agent quality, prompt changes, perf+accuracy tradeoffs), build the evaluation harness before iterating. Distinct from TDD: that's correctness, this is regression detection on fuzzy outputs. Without a number, every "improvement" is just changing posture.
- **Stop-the-line for missing infra**: When you hit a regression you can't bisect or a "did this help?" you can't answer, halt feature work and build the harness/CI first. This overrides one-shot delivery—the harness is a separate prerequisite deliverable, not phasing. Resume the feature as its own one-shot diff after. The cost of not having it compounds faster than the cost of building it.

#### Judgment & upkeep
- **Code is cheap**: Implementation time is never a reason to pick the hack—build the durable, structurally-correct fix even when it takes much longer. Durable means correct, not bigger: keep scope to what the request needs. Self-check: *am I hacking to save time, or padding scope and calling it "durable"?* Reject both.
- **Self-improvement**: After meaningful corrections, propose a concise rule for CLAUDE.md. Self-check: *would this rule have caught a different past mistake, or apply to a future task unrelated to this one?* If not, mention it in the reply and move on—don't bloat the file.
- **Context discipline**: Keep progress narration terse and useful. Summarize large logs, file dumps, and generated artifacts instead of pasting them into the conversation unless exact text is needed.

### Code

- **Minimal changes**: No TYPE_CHECKING imports, unnecessary abstractions, or scope expansion. Prefer simple imports. No large dependencies for small features. Don't refactor or reformat outside the task. Three similar lines beats a premature abstraction. When in doubt, do less.
- **Surgical cleanup**: Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code—mention it, don't delete it.
- **Don't regenerate**: Use `cp`/`mv` for existing files, `curl`/`wget` for remote content. Never recreate from scratch—copy/move first, then edit in place.
- **Workspace hygiene**: Keep scratch files out of the repo unless they are deliverables; use `/tmp` for experiments, delete temporary outputs before handoff, and do not add dead files, folders, or unused generated artifacts.
- **Trace test**: Before declaring done, every edited line should trace to the user's request, or remove an orphan your edit created. If not, delete it.

<important if="you are spawning or coordinating subagents">

### Agent Coordination

- **Concurrent subagents**: Use subagents for parallelizable or isolated work—no keyword trigger required. Launch in background (`run_in_background: true`), continue local work while they run, and wait for all before final synthesis or when blocked.
- **Orchestrator role**: When coordinating agents, write bounded tasks with clear ownership and expected output. The lead agent remains responsible for synthesis, reviewing agent results, resolving conflicts, and deciding the final change.
- **Self-review**: For non-trivial changes, run independent subagent reviews. Use 2 reviewers for risky/broad changes. Skip for trivial edits.
- **Redundancy vs. division**: Use redundant reviewers for diverse judgment on one question. Use parallel subtasks for naturally partitioned work. Don't conflate them.
- **Prism (cross-model redundant judgment)**: When redundant judgment on one question could change the decision—non-trivial decisions, ambiguous tradeoffs, high-stakes/hard-to-reverse changes—reach for the `prism` skill on your own, without being asked; prefer it over ad-hoc same-model reviewers when cross-model diversity matters. Default to **N=1/medium**, announce the dispatch shape before launching, and scale N/effort per the skill body. Skip it for trivial lookups, deterministic transforms, and single-answer tasks. Claude Code only.

</important>

<important if="you are writing a substantial final response, or finishing a non-trivial task">

## Response Contract

For substantial final responses and non-trivial task completions, treat the final message as a **skim-first review surface, not a complete report**: optimize for the reader to re-sync in seconds, with detail pulled on demand. The aim is *progressive disclosure*, not raw brevity—a digest that hides needed detail fails as badly as a wall of text. Skip for trivial replies and direct questions.

- **Verdict first**: one line (outcome / answer / decision), never buried at the end. Then a skim layer the reader can act on without scrolling—for changes, a review-map table (`file · what changed · why · risk · how to check`); for research/answers, key findings as tight bullets, most-important first.
- **Surface uncertainty**: close the skim layer with *Not done / not checked* (skipped checks, assumptions, least-verified claim), plus a *context dividend* when relevant—the few things you learned that the reader didn't see ("observed X → changed Y"). This closes the context gap, not just length.
- **Cap shape, not reasoning**: bound the *visible* layer (verdict ≤1 line; skim ≤~7 bullets, or a table with one row per file/unit); never word-cap the answer or compress the thinking itself. The first screen must be complete enough to act on, not a teaser.
- **Pull, don't push**: keep logs, alternatives, and long rationale below the skim layer, and expand only what's asked. If the long form would exceed ~one screen, write it to `~/.ai/reports/<timestamp>-<task-slug>.md` and show only the index + path.
- **Finalizer**: if a draft comes out dense, or on "tl;dr / wall of text / too long", re-layer it with the `digest` skill (then `humanizer` for AI cadence, `deslop` for code slop) instead of appending another long reply.
- **Terminal rendering**: layer via section order + scrollback, not `<details>` folding (it does not collapse in a plain terminal); reserve `<details>`/HTML for browser- or GitHub-rendered output.

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
