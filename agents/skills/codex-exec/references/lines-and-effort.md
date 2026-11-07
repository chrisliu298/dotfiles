## Lines

Each task line is one Codex thread with its own worktree and branch, kept in a tmux session
`cx-<name>`. Closing the session keeps the thread, worktree
and branch, so a line can be closed when idle and resumed later with its context.

Codex runs GPT-6.1 Sol, launched as the user's own `x` launcher does (`--yolo`) from an
interactive shell, so it has the user's permissions, environment and credentials: no
approvals, no sandbox, full network and SSH. It reads [executor.md](../executor.md) with every
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
level.

