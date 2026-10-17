---
name: codex-exec
description: |
  Hand planned implementation work to a Codex executor that works in its own git worktree and
  tmux session, then verify its result. Use proactively, without being asked, once a task's plan
  and boundaries are settled and its result can be checked independently: changes across
  several files, implementation with test iterations, scripted dev-machine or short platform
  runs. Also use when the user asks for Codex to execute ("让 codex 执行", "codex 来做", "cx"),
  to open, continue, close or list executor lines, or when a "[cx <line>]" message arrives.
  Not for read-only review or discussion (agent-team).
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

## Lines

Each task line is one Codex thread with its own worktree and branch, kept in a tmux session
`cx-<name>`. Closing the session keeps the thread, worktree
and branch, so a line can be closed when idle and resumed later with its context.

Codex runs `gpt-6-astra`, launched as the user's own `x` launcher does (`--yolo`) from an
interactive shell, so it has the user's permissions, environment and credentials: no
approvals, no sandbox, full network and SSH. It reads [executor.md](executor.md) with every
message: it commits all its work, may push its branch and submit short platform jobs; merge requests, merges, training jobs, job priorities and messages to
people stay with you.

## Effort

Choose each line's effort when you start it (`--effort`, default `high`); `cx effort NAME
LEVEL` changes it from the line's next open. OpenAI's guidance: in Codex, start from the
model's default (medium for Astra), lower it for simpler tasks and raise it for deeper
analysis ([GPT-6 model guide](https://openai.com/index/practical-guide-building-gpt-6/));
high and xhigh suit "difficult work with multiple steps, sources, or tradeoffs"
([Codex models](https://learn.chatgpt.com/docs/models)); high is "recommended for complex
workflows and agentic tasks", and xhigh is for "only when your evals show a clear benefit"
([reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)). Astra accepts
low, medium, high, xhigh and max
([model page](https://developers.openai.com/api/docs/models/gpt-6-astra)). In practice:

| Level | For |
| --- | --- |
| `low` | mechanical, well-scoped edits: renames, doc fixes, applying a fully specified diff |
| `medium` | a routine change in one module with clear tests |
| `high` | multi-file or cross-module work, platform or dev-machine steps, unclear failures |
| `xhigh` / `max` | only after a line at `high` fell short on the same kind of task |

When a line fails acceptance for lack of reasoning rather than a bad plan, raise it one level.

## Commands

`scripts/cx` beside this file (resolve its installed location):

```bash
cx start NAME [--effort LEVEL] [--repo DIR] [--base REF] [--branch BRANCH] < task.md
cx send NAME < message.md      # follow-up or rework; resumes a closed line first
cx wait NAME [--timeout S]     # until the turn that got the latest message ends; prints the reply
cx diff NAME                   # uncommitted files, commits and diff since the line's base
cx effort NAME LEVEL           # low|medium|high|xhigh|max, from the next open
cx open NAME                   # resume a closed line without a message
cx attach NAME                 # watch or type in the session (for the user)
cx close NAME                  # end the tmux session; thread, worktree and branch stay
cx ls                          # lines: open/working/closed, effort, latest message, branch
cx rm NAME [--force]           # after merge: remove worktree and line state; branch stays
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
it passes, carry on with the repository's normal flow (review, merge request, merge), then
`cx rm` the line. Code Codex wrote still goes through the repository's usual review; the
executor line is never a reviewer of its own work.
