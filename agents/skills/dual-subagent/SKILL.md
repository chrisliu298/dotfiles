---
name: dual-subagent
description: |
  Delegate read-only tasks to Claude Code and Cursor Agent concurrently, including
  research, reading, analysis, diagnosis, checks, review, and audit. Use when
  the user requests this skill, asks both agents, or the applicable delegation
  rules route a read-only task here. Tasks requiring file or external-state
  changes belong to native subagents.
---

# Dual Subagent

Use Claude Code and Cursor Agent as two independent one-shot collaborators. They
run concurrently in the command's working directory and receive the same prompt.

## Run both read-only contributors

1. Define one bounded, read-only assignment. Include the goal, relevant paths,
   known constraints, expected deliverable, and non-file conversation context
   the subagents cannot infer. Explicitly prohibit file and external-system
   changes.
2. Put the prompt in a scratch file outside the repository. Invoke the
   `scripts/dual-subagent` helper beside this `SKILL.md` from the target working
   directory, piping the prompt on stdin. The helper starts the existing Claude
   and Cursor subagent helpers concurrently and waits for both.
3. Use `--effort high` by default. Use `--effort xhigh` for difficult problems;
   the helper maps the same choice to both subagents. Do not use other effort
   levels.
4. Pass `--trust` only after confirming the current workspace is one the user
   intends Cursor to access. This affects Cursor Workspace Trust only.
5. On macOS, Cursor Agent reads its login from Keychain. If the command runner
   sandboxes Keychain access, invoke the entire dual helper with that runner's
   narrowly scoped unsandboxed/elevated execution option from the outset; the
   Cursor child inherits the dual helper's execution context. Scope any
   persistent approval to the dual helper path. `SecItemCopyMatching failed
   -50` followed by exit 139 is an execution-context failure, not evidence that
   the Cursor login or pinned model is invalid.
6. The helper's default timeout is 7,200 seconds (2 hours). Keep that long
   default rather than guessing how quickly unfamiliar work should finish. Pass
   `--timeout-seconds N` only when the user requests a different bound or when
   performing a controlled helper test.
7. Start one helper call and wait on that same process. If the command tool
   yields a running-session identifier, resume it; do not submit duplicate
   requests merely because one or both subagents have not produced output yet.

Example command shape:

```bash
"${CODEX_HOME:-$HOME/.codex}/skills/dual-subagent/scripts/dual-subagent" --effort high --trust < /tmp/dual-subagent-prompt.md
```

The helper prints separate `CLAUDE` and `CURSOR` sections and succeeds only when
both calls return successfully with non-empty output. If either fails, retain
the successful contribution, label the result partial, inspect the workspace,
and report the failed peer. A failed peer may be retried at most twice, for no
more than three attempts total for that peer; do not rerun a peer that already
succeeded. Each retry must follow workspace inspection. At the deadline it
terminates only peers still running, then emits any completed peer as a partial
result. Never retry blindly after a call that might have changed files or
external state. For Claude, do not classify its known
`[claude-code:unrecognized_model]` stderr diagnostic as a failure or consume a
retry for it: it comes from the session-title side channel, not the delegated
request. Keep waiting for that same Claude process and judge it only after exit,
using its exit code and stdout.

The Cursor helper can recover a complete final response when Cursor finishes
the answer but then raises `WritableIterable is closed` while closing its
output stream. In that case the helper exits zero and the dual call is complete;
do not count it as a failed peer or retry it.

## Synthesize independently

Do not ask either subagent to see or critique the other's response. After both
return, compare them yourself:

- Identify conclusions and evidence they independently agree on.
- Preserve useful findings unique to either response.
- Surface disagreements instead of resolving them by majority vote.
- Verify consequential claims against the repository, tests, or primary sources
  before presenting them as confirmed.

Present Claude and Cursor as delegated contributors, not as independently
verified authorities.

## Route by whether changes are required

Use this skill for delegated research, reading, analysis, diagnosis, checks,
review, and audit that do not modify files or external state. A read-only task
can be completed here; it does not need to be framed as a review of prior work.
For example, both contributors can inspect source documents and explain a
training failure without editing code or changing the running job.

Use native subagents only for assignments that require changes to files or
external state. Split mixed assignments: dual produces findings or a proposed
change in its response; the lead or a native subagent applies the changes.
Routine scratch output and helper logs are permitted; do not treat them as
permission to modify project artifacts, configuration, or external resources.
The lead may handle simple tasks directly; delegation is not a mandatory stage.

## Safety

The Claude helper can use write and shell tools even when the prompt says
read-only; Cursor is forced into `--mode ask`. The user's authorization remains
the boundary. Keep both assignments inside the current task, state the
read-only constraint explicitly, and do not pass secrets unnecessarily.
