## Lines

Each task line is one Codex thread with its own worktree and branch, kept in a tmux session
`cx-<name>`. Closing the session keeps the thread, worktree
and branch, so a line can be closed when idle and resumed later with its context.

Codex runs GPT-6.1 Sol on the user's subscription, launched as the user's own `x` launcher does (`--yolo`) from an
interactive shell, so it has the user's permissions, environment and credentials: no
approvals, no sandbox, full network and SSH. It reads [executor.md](../executor.md) with every
message: it commits all its work, may push its branch and submit short platform jobs; merge requests, merges, training jobs, job priorities and messages to
people stay with you.

## Ark

When the user asks for Ark (方舟) or Astra, or a user-facing resident `*-r2v` Claude
session delegates a difficult task under its standing authorization in global AGENTS,
pass `--ark` to `cx start`. That exception excludes agent-team Claude instances and other subagents.
Ark replaces the subscription for that line; it is not a second line. The line then runs through `codex-ark` on Ark's GPT-6-Astra endpoint, or GPT-6.1-Sol
when the user asks for Sol (`ARK_MODEL=sol cx start ... --ark`). The choice is fixed when the line starts and kept
across `open`, `send` and resume; a line cannot switch between Ark and the subscription. Never
choose Ark without explicit user request outside the resident `*-r2v` Claude difficult-task exception,
or switch providers as an automatic rate-limit fallback; report that instead.
An Ark 429 is the endpoint's rate limit: report it, and use Sol only if the user asks.

## Effort

Every line otherwise runs GPT-6.1 Sol on the subscription; there is no model to choose. There is no default effort: decide
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

