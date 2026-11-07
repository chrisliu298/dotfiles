## When to use

Only delegate to Codex when the user explicitly requests it for this work.
Otherwise do the work yourself or use the host's native subagent when delegation helps.
For authorized Codex work, hand off once the plan and its boundaries are settled and
you can check the result independently: changes spanning several files,
implementation with test iterations, scripted runs on dev machines, short platform jobs. Do it
yourself when writing the plan would take longer than the change (a one-line fix, a doc edit),
when the next step depends on what you learn while doing it (exploratory diagnosis stays with
you; hand off the fix once the cause is known), or when the work stays with you by role (merge
requests, training jobs, job priorities, messages to people). Keep one line per independent piece of work; parallel lines are fine
when their files do not overlap.

For authorized Codex work, check whether you can write the acceptance commands now.
If you cannot, the work still depends on what this conversation is learning: keep it,
or use a native subagent with enough context. Native subagents may implement changes
as well as perform read-only work; give each bounded ownership and verify its result.
A Codex line is not a native subagent: when the user asks for a subagent without naming Codex, use the native Agent
tool, not a line.

