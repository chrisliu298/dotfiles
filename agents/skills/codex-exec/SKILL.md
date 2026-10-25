---
name: codex-exec
description: |
  Hand settled implementation work to a Codex executor in its own worktree and tmux session,
  then verify the result. Use proactively once a plan is settled and checkable (multi-file
  changes, test iterations, scripted runs); also when the user asks Codex to execute
  ("让 codex 执行", "cx"), to manage executor lines, or on a "[cx <line>]" message. Not for
  review (agent-team).
---

# Codex executor

You plan and verify; Codex executes. Handing off execution does not make your part smaller:
planning and verification are often most of the work, and a well-made plan is what makes
execution simple. Before sending a task, read the code it touches, check its premises, and
make the design decisions yourself; after it returns, verify as if you had not seen the plan.

## When to use

Decide yourself; the user does not need to ask. Hand off once the plan and its boundaries are
settled and you can check the result independently: changes spanning several files,
implementation with test iterations, scripted runs on dev machines, short platform jobs. Do it
yourself when writing the plan would take longer than the change (a one-line fix, a doc edit),
when the next step depends on what you learn while doing it (exploratory diagnosis stays with
you; hand off the fix once the cause is known), or when the work stays with you by role (merge
requests, training jobs, job priorities, messages to people). Keep one line per independent piece of work; parallel lines are fine
when their files do not overlap.

The test is whether you can write the acceptance commands now. If you can, the work goes to a
line, not to a fresh native subagent, which has neither this conversation's context nor its own
worktree and is checked by the same model that wrote it. If you cannot, the work still depends
on what this conversation is learning: keep it, or fork yourself so the fork inherits that
context. Fresh native subagents stay on read-only searches and analysis.

## Lines

Each task line is one Codex thread with its own worktree and branch, kept in a tmux session
`cx-<name>`. Closing the session keeps the thread, worktree
and branch, so a line can be closed when idle and resumed later with its context.

Codex runs GPT-6.1 Sol, launched as the user's own `x` launcher does (`--yolo`) from an
interactive shell, so it has the user's permissions, environment and credentials: no
approvals, no sandbox, full network and SSH. It reads [executor.md](executor.md) with every
message: it commits all its work, may push its branch and submit short platform jobs; merge requests, merges, training jobs, job priorities and messages to
people stay with you.

## Effort

Every line runs GPT-6.1 Sol; there is no model to choose. There is no default effort: decide
each line's effort from its task with the table below and pass it to `cx start` (`--effort`),
which refuses to start without it. Decide again when a line's next message is a different kind
of work, such as a hard failure to diagnose after a mechanical edit: `cx effort` changes it
from the next open.

Start Sol at low and raise it for tasks that need more planning, analysis or checking
([Codex models](https://learn.chatgpt.com/docs/models)). Your plan carries most of the
reasoning, so an executor line rarely needs more:

| Effort | For |
| --- | --- |
| `low` | most lines: mechanical edits and implementation from a settled plan, with tests and rework rounds |
| `medium` | cross-module work, dev-machine or platform steps, failures to diagnose |
| `high` | conflicting evidence, or a failure that `medium` did not crack |
| `xhigh` | only after `high` fell short on the same kind of task |

When a line fails acceptance for lack of reasoning rather than a bad plan, raise its effort one
level. Leave `max` alone, and Codex's `ultra`, which delegates to subagents, out of executor
lines.

## Commands

`scripts/cx` beside this file (resolve its installed location):

```bash
cx start NAME --effort LEVEL [--repo DIR] [--base REF] [--branch BRANCH] < task.md
cx send NAME < message.md      # follow-up or rework; resumes a closed line first
cx wait NAME [--timeout S]     # until the turn that got the latest message ends; prints the reply
cx diff NAME                   # uncommitted files, commits and diff since the line's base
cx effort NAME LEVEL           # low|medium|high|xhigh|max, from the next open
cx open NAME                   # resume a closed line without a message
cx attach NAME                 # watch or type in the session (for the user)
cx close NAME [--force]        # end the tmux session; thread, worktree and branch stay
cx ls                          # lines: state, effort, latest message, owner, branch
cx rm NAME [--unmerged|--force]  # when done: remove worktree and line state; branch stays
```

`start` creates the worktree from a fresh `origin/main` by default on branch `codex/NAME`;
pass `--branch` when the repository names branches by convention. Lines live in
`~/.local/share/cx/NAME/` (`msg-NNN.md` sent, `reply-NNN.md` received, `ask-NNN.md` questions,
`wt/` worktree).

After `start` or `send`, run `cx wait` in the background so its completion notifies you, and
keep doing independent work. `send` to a running line steers the message into the current turn
and confirms Codex received it (exit 124 when it cannot; inspect before resending). `wait`
returns only for a turn that received the latest message, so an earlier turn ending never
passes for it. A finished `wait` is the turn's end, not proof the task is done.

## Questions from Codex

Codex asks with `cx ask` when a decision is yours. It reaches this session as a cross-session
message starting with `[cx <line>]` that names a question file. Read the file, decide, write
the answer to a scratch file and send it with `cx send <line> < answer.md`; do not answer with
SendMessage, since the sender is a one-shot relay that has already exited.

`cx wait` reports the end of one turn, nothing more; a reply that ends with a question is not
acceptance. After every `cx send`, answers included, start a new background `cx wait`: it binds
to that latest message, while a wait started earlier stays bound to its own message and may
return before the answer's turn ends.

## Closing and resuming

Lines outlive your turn and your context, so close or remove each one as its state calls for.
A line belongs to the Claude session that last started, sent to or opened it successfully,
which is where `cx ask` questions go; `cx ls` shows it as OWNER (`me` for you), and `attach`
does not change it. Act only on your own lines or ones the user hands you; a `cx send` or
`cx open` from a restarted session takes a line over.

| Situation | Do |
| --- | --- |
| A turn is running, or someone is attached | leave it; `close` and `rm` refuse (`--force` kills the session mid-turn) |
| The reply is in and you are verifying or sending rework | keep it open |
| Codex is done and you wait on review, CI, a platform job it submitted, or the user | `cx close`; a later `cx send` resumes the same thread with its context |
| Merged, accepted with nothing to merge (a scoring or export run), or dropped, with no known follow-up | `cx rm`; the line can no longer be resumed |
| Your task ends, or you continue after a compaction or restart | `cx ls`; close your idle lines that expect no message soon, and note the closed ones you may resume, with any pending question and job ID, in your handoff |

Remove a line only when nothing is known to come back to it: a merge request in review, an
open follow-up on the same branch, or a platform job whose result may need a fix keeps it
closed instead, so the fix reuses the thread's context. `rm` refuses uncommitted changes and
commits not on origin's default branch; `--unmerged` waives only the latter (after a squash
merge, or to drop committed work), and `--force` waives every check.

## Task message

Write the task to a scratch file outside the repository and pipe it to `start` or `send`:

- **Goal**: the outcome and why, in a few lines.
- **Plan**: numbered steps, with the files, functions, and decisions you already made.
- **Acceptance**: commands to run and what they must show, plus one number you can
  recompute independently (a count, SHA, or metric).
- **Constraints**: anything beyond executor.md and the repo's AGENTS.md that applies.
- **Context**: facts Codex cannot find in the repo (user decisions, job IDs, paths on dev
  machines).

Keep the plan at the level of decisions; leave mechanical detail to Codex.

## Verify

Codex's reply is a claim. Before accepting:

1. Run `cx diff NAME`: nothing uncommitted, then read every commit and the full diff since
   the line's base.
2. Rerun the acceptance commands yourself, or recompute the number by an independent route.
3. Check the diff stays within the plan and the repository's rules.

If anything fails, `cx send` the specific failure and what to change, then wait again. When
it passes, carry on with the repository's normal flow (review, merge request, merge), and
close or remove the line as "Closing and resuming" says. Code Codex wrote still goes through the repository's usual review; the
executor line is never a reviewer of its own work.
