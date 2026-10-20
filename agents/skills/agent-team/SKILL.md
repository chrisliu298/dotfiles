---
name: agent-team
description: Delegate read-only analysis, research, planning or review to the gpt (Codex), claude, gemini, muse, ds (DeepSeek) and pro (ChatGPT Pro) backends, alone or in parallel. Use when the user names one of them for such a task or asks for this skill; pro alone goes to the gpt-pro skill. Not for implementation.
---

# Agent Team

The user chooses the backend, not a
model or effort tier. Each backend runs with its pinned model and effort: `xhigh`
for gpt and claude, `high` for the rest; no model, effort, or mode selection
options are exposed. Every backend runs with the
same full access as the user's own launchers: no approval prompts, no sandbox, and
network access (including SSH to dev machines). Read-only scope is an assignment
instruction, not a permission boundary. Default to a persistent session;
use `--once` only for a request that needs no follow-ups.

## Choose reviewers

Read the user's message for backend names and assignments:

- “让 Claude 审查” → `claude`.
- “Claude 和 Gemini 并行独立审查” → `claude` and `gemini`, same assignment.
- “GPT、Claude、Gemini、Muse、DeepSeek 都看一下” → `gpt`, `claude`, `gemini`, `muse`
  and `ds`, same assignment.
- “也问问 Pro” / “ChatGPT Pro” alongside other backends → `pro`.
- “Claude 看正确性，GPT 看测试” → `claude` and `gpt`, distinct assignments.

Each backend runs at most once per call; a repeated `--backend` is rejected. When
the user asks for more reviewers than distinct backends, say so and ask how to
split the work. Start every reviewer with one `start` call: backends without a
file share the stdin prompt, and `--backend NAME=FILE` gives a backend its own
assignment (an absolute path or one relative to the working directory). Write one backend-neutral prompt; the helper adds
each backend's completion and launch details, so do not tailor prompts per
backend or add deadlines (`wait --timeout` bounds the wait). `--file PATH`
(repeatable) shares local files: `pro` cannot open paths, so its prompt inlines
their contents, while the other backends receive the absolute paths to read.
If no backend was chosen and the request does not identify one, ask which to use.
An unspecified “subagent review” remains the caller's native subagent workflow.
Always name backends by these ids, in prompts, reports and attribution alike:
`gpt` is Codex CLI; `claude` is Claude Code; `gemini` is Cursor Agent on Gemini;
`muse` is Muse Code; `ds` is DeepSeek through Claude Code; `pro` is ChatGPT Pro
through the gpt-pro relay. Product names describe only the underlying tool.

Before dispatch, read only the references for the chosen backends:
[`gpt`](references/gpt.md), [`claude`](references/claude.md), [`gemini`](references/gemini.md),
[`muse`](references/muse.md), [`ds`](references/ds.md), [`pro`](references/pro.md).
Use `scripts/agent-team` beside this `SKILL.md`; resolve its actual installed
location rather than assuming a particular agent's skill directory. It requires
Node.js and zsh, plus tmux for persistent sessions other than `pro`. `backends` reports configured
availability, not a verified login or model entitlement. This skill is installed
for Claude Code only. Report unavailable backends; do not substitute one.

## Persistent task

Write a bounded read-only assignment to a scratch file outside the repository:
goal, relevant paths, constraints, expected deliverable, and conversation context.
The deliverable can be an analysis, a research synthesis, a proposed plan, or a
review. Preserve the user's requested task rather than turning every assignment
into a code review. Backend tool capabilities still limit what can be executed.
Explicitly prohibit file and external-system changes. Native reviewer subagents
may handle bounded parts under the same scope unless the user says otherwise.
The reviewer owns its evidence and synthesis; a child failure matters when it
leaves an unresolved coverage gap. Nested review-helper calls are blocked.

From the authorized working directory:

```bash
# helper is scripts/agent-team beside this SKILL.md.
$helper backends
session="$($helper start --backend claude < /tmp/review.md)"
# Same assignment for gpt, gemini and muse, a distinct one for claude:
$helper start --backend gpt --backend gemini --backend muse \
  --backend claude=/tmp/claude-review.md < /tmp/review.md
# pro receives the file contents; claude receives the path:
$helper start --backend pro --backend claude --file src/main.py < /tmp/review.md
$helper wait "$session"
$helper send "$session" < /tmp/supplement.md
$helper wait "$session"
$helper stop "$session"

# A multi-backend start returns a JSON manifest of independent sessions.
$helper start --backend claude --backend gpt --backend muse < /tmp/review.md
# Read session handles from the manifest; later actions infer each backend.
$helper wait "$session1" "$session2" "$session3"
$helper send "$session1" "$session2" "$session3" < /tmp/supplement.md
$helper wait "$session1" "$session2" "$session3"
$helper stop "$session1" "$session2" "$session3"
```

Single-backend start prints its session name. Multi-backend start returns
`{"sessions":[{"backend":"claude","session":"..."}],"errors":[],"is_error":false}`.
Inspect the exit code and errors. A partial startup returns nonzero while retaining
successful handles: collect those reviews and stop their sessions; do not retry the
whole batch. Startup handles are also printed to stderr as they arrive, for recovery
if the caller is interrupted. A handle proves dispatch, not a completed review.

After start and every supplement, run `wait` and collect that same waiter to
completion. If the command tool yields a running process ID, resume it instead
of launching another waiter. Use background completion notification when the
caller supports it; otherwise await the process while doing independent work.
Completion notification applies to the active caller turn, not a finished one.

`wait` returns the full reply, including backend/session attribution for multiple
sessions. Never use a quiet screen or `capture` as proof of completion. A finished
turn still needs the requested findings and deliverable; an opener is unfinished
work. Continue the same session with a focused request to finish missing coverage.
Verify consequential claims against primary artifacts and produce the requested
deliverable. For multiple contributors, preserve attribution and identify relevant
agreements, disagreements, and remaining gaps.

## Control and failure semantics

- `send` returns JSON with `delivery`. `gemini` `confirmed` means steering activation
  or transcript receipt was confirmed, not that the message has joined the turn yet
  (steering waits for the next safe boundary, as on the other backends); `pro`
  `confirmed` means the relay acknowledged delivery into the running answer.
  `claude`/`gpt`/`muse`/`ds` `submitted` means text was pasted and Enter sent; it
  does not independently prove consumption or task completion. Use `wait` for the
  resulting reply. Do not interrupt merely to add context.
- A `pro` conversation accepts no follow-up once its answer finishes: `send` fails
  and says to start a new task that includes the answer and the new question.
- `gemini` and `pro` `unconfirmed` return 124; the message may still be queued. Inspect it or
  keep waiting, without automatically resending or restarting.
- A failed `send` leaves that session's latest request failed. `wait` reports the
  failure instead of returning its previous reply; a subsequent successful send
  clears it. In a batch, retain failed delivery entries separately from completed
  replies. Do not treat them as answers to the supplement.
- `wait SESSION [SESSION ...] --timeout N` defaults to 3600 seconds per session,
  7200 for `pro`.
  Timeout returns 124 when all failures are timeouts; mixed failures return 1.
  Multi-session replies retain individual exit codes and diagnostics.
- `status` and `capture` are diagnostic. `input_ready=1` does not prove the model
  is idle. `interrupt` requests an urgent stop using the backend's native key;
  it does not guarantee background work was cancelled. Inspect before new work.
  Interrupting `pro` stops its run for good.
- `list` includes sessions started by earlier entrypoints. Session actions do not
  require the backend to remain available, so cleanup is still possible.

On failure, inspect output/pane and the workspace before a safe retry. Allow at
most two retries, never duplicate a running request or a message that may already
be queued. Stop every session you started before the final answer; keep one only
when follow-ups are needed and explicitly name it as open. Stop only named sessions,
never the tmux server.

## One-shot task

```bash
$helper --once --backend gpt < /tmp/review.md
$helper --once --backend gpt --output-format json < /tmp/review.md
$helper --once --backend claude --backend gpt < /tmp/review.md
$helper --once --backend claude --backend gpt --timeout 300 < /tmp/review.md
$helper --once --backend gpt=/tmp/a.md --backend muse=/tmp/b.md
```

Single text mode returns the final reply. Single JSON mode uses
`{"result":"...","exit_code":0,"is_error":false}`. Multi-session and multi-backend
one-shot actions return `{"results":[{"backend":"...","result":"...","exit_code":0,"is_error":false}],"is_error":false}`.
Each one-shot backend has a 3600-second deadline (`pro` 7200), configurable with `--timeout`.
Timeout returns 124 and stops the owned process group, including descendants.
Each completed one-shot reply is immediately recorded on stderr as a JSON line
with `event: "completed"`, backend and the same result fields. Save
these records if the caller stops before the final stdout manifest; do not rerun
already completed assignments. SIGINT/SIGTERM stops unfinished process groups
and returns the collected manifest with exit code 130/143.

Nonzero exits and empty replies from either `wait` or `--once` are failures. The helper never changes login,
installs missing dependencies, chooses a replacement backend, or merges the reviews
itself; the calling agent performs verification and synthesis.
