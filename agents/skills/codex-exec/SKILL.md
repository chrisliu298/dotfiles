---
name: codex-exec
description: |
  Hand settled, checkable implementation (multi-file changes, test iterations, scripted runs) to
  a Codex executor line only when the user explicitly requests Codex, then verify it.
  Handle line management and executor replies for already authorized work.
  Default delegation uses the host's native subagent, not this skill. Not for review (agent-team).
---

# Codex executor

You plan and verify; Codex executes. Handing off execution does not make your part smaller:
planning and verification are often most of the work, and a well-made plan is what makes
execution simple. Before sending a task, read the code it touches, check its premises, and
make the design decisions yourself; after it returns, verify as if you had not seen the plan.

## Execution boundaries

Start or assign work to a Codex line only when the user explicitly requests Codex
for that work. A settled plan, a multi-file change, or a request for parallel work
is not authorization. When delegation helps, use the host's native subagent by default,
including for implementation. Existing authorized work may finish with necessary
clarifications and rework; a peer reply or a resumed line does not authorize new scope.

A Codex line is a separate thread/worktree, not a native subagent. A bare request
for a subagent uses the native Agent tool. Only act on your own lines or ones the
user hands you. Merge requests, merges, training jobs, job priorities and messages
to people remain with you, not the executor. The line's full access does not expand
the assignment. Its ongoing executor contract is [executor.md](executor.md).

A completed turn or `cx wait` is not task acceptance. Do not close/remove an active
line or treat a pending question as a finished task.

## Read the relevant procedure before acting

Resolve bundled files and `scripts/cx` from this skill root; scratch messages and
project commands keep their own working directories. Read only the relevant
procedures, including their prerequisites.

- Before deciding to delegate: [Planning and scope](references/planning.md). Settle the design and acceptance commands first; exploratory work stays with you.
- Before starting a line: read [Lines and effort](references/lines-and-effort.md), [Commands](references/commands.md), [Task message](references/task-message.md) and [Verification](references/verify.md). Model and effort behavior remain as specified there; pass an explicit task-appropriate effort.
- Send, wait, inspect a diff, or change effort: [Commands](references/commands.md). Before selecting/changing effort, sending a different kind of task, or reworking a failure caused by insufficient reasoning, also read [Lines and effort](references/lines-and-effort.md). After each send, collect a new waiter bound to that message.
- Handle a `[cx LINE]` question: [Questions from Codex](references/questions.md), then use the command procedure to send the answer and wait again.
- Accept or request rework: [Verification](references/verify.md). Verify the actual diff and acceptance evidence independently.
- Close/remove/resume a line, finish your task, or continue after compact/restart: [Lifecycle](references/lifecycle.md); resume also uses [Commands](references/commands.md). Inspect ownership and state first; preserve threads with known follow-ups.
