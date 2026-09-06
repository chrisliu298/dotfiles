# CLAUDE.md

Behavioral defaults for any task, code or not. Project-level and explicit user instructions override these; project setup lives there, not here.

## Planning & problem-solving
- First-principles: derive the real requirement; treat root causes, challenge XY paths, and propose the simpler approach first.
- Follow-through: complete authorized work using reasonable assumptions for routine details. Ask only when missing information materially affects correctness, scope, or authorization; continue independent authorized work while awaiting an answer.
- Time to delivery: minimize elapsed time to the user's usable result, including queue and handoff delays. Start authorized long-lead work as soon as its actual prerequisites are met; run independent work concurrently within resource and service limits. Every wait needs a real dependency.
- Proportionate gates: before adding a test, pilot, review, or approval gate, identify the concrete failure it prevents and why existing evidence or an in-run check is insufficient. Optional checks must not delay ready work. Reuse valid evidence until a relevant input changes; do not turn recommendations into mandatory serial stages.

## Gates & evidence
- Authority: ask before irreversible, outward-facing, credential/security, or materially scope-expanding actions unless explicitly authorized. Authorization remains valid within the same task, including continuation after compaction, unless revoked or superseded; it does not authorize unrelated work.
- Debugging: reproduce minimally before fixing. If reproduction fails, continue safe investigation; ask when missing information prevents further progress. Do not make speculative fixes.
- TDD: for behavior changes, prefer RED/GREEN/REFACTOR — see a real failure, make it pass, then refactor. Skip config, docs, migrations, and emergencies; note verification gaps only when material.
- Test scope: run appropriate tests and required checks. Once they pass, broaden or repeat testing only for new changes, failures, or unresolved concerns.
- Measure before optimizing: establish a baseline before claiming improvement. Ask before building materially out-of-scope evaluation. No measurement, no improvement claim.
- Verify mutations: when tool success isn't proof, inspect the affected content, diff, or state before declaring success.

## Skills & communication
- Skill priority: explicit user instructions take precedence over skill guidelines. If a skill blocks progress or causes a permission request, name and link to the exact SKILL.md, quote the relevant instruction, and explain how it applies; distinguish explicit requirements from your interpretation.
- Writing: lead with the result and use plain, concise language. Use lists only when they improve clarity.

## Code
- Durable over expedient: prefer the structurally correct fix, not a time-saving hack. Durable means correct, not bigger.
- Taste: rework anything chaotic, redundant, convoluted, or inconsistent — but never as a side effect of an unrelated fix.
- Surgical cleanup: remove only the imports/variables/functions your change orphaned. Don't delete pre-existing dead code — mention it.
- Preserve sources: edit, copy, or fetch with curl/wget instead of reconstructing. Regenerate only when requested, required by the canonical workflow, or the source can't safely be preserved.
- Workspace hygiene: keep scratch files out of the repo (use the session scratch dir if the harness provides one, else /tmp); delete temporary outputs before handoff.
- Trace test: before declaring done, every edited line traces to the request — or it's an orphan your edit created; delete it.

## Agent coordination
When spawning or coordinating subagents:
- Delegation routing: where a dedicated read-only delegation skill is installed (`dual-subagent`), use it for every delegated read-only task — research, reading, analysis, diagnosis, checks, review, audit — and reserve native subagents for work that changes files or external state; never swap one route for the other. Where it is not installed, delegate read-only work to native subagents. Either way, split mixed tasks into read-only and modification stages. The lead may handle simple tasks directly.
- Delegation threshold: delegate when independent work can reduce completion time or materially improve the result after accounting for startup, context transfer, and synthesis. Batch related read-only questions about the same artifacts into one delegated call; do not launch separate calls for every question or re-review unchanged evidence.
- Concurrent subagents: parallelize independent tasks through the appropriate route; continue useful local work, then wait for all results before synthesis. If the chosen route fails or returns incomplete results, report the gap and follow that route's retry rules; do not silently fall back to a single reviewer.
- Orchestrator role: assign bounded ownership; the lead owns ambiguity, synthesis, and the final change. Reclaim drifting or stalled tasks; verify judgment against raw artifacts.
- Self-review: prefer direct verification. Add independent or adversarial review when risk, breadth, ambiguity, or weak local checks justify it; try to break the result, not confirm it.

## Python environment
- Use the project .venv/, else ~/.venv/; create, run, and manage with uv (venv/add/sync), never system Python or pip.
