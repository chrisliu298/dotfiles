---
name: cursor-subagent
description: |
  Obtain an independent read-only review from Cursor Agent using a pinned
  GPT-5.6 Sol model. Use when the user asks to "ask Cursor", "use Cursor as a
  reviewer", get a "Cursor take", or obtain an independent Cursor review or
  second opinion. Do not use this skill to implement, complete, advance, or
  operate a task; use Codex's native subagents when delegated execution is
  requested.
metadata:
  surfaces:
    - codex
---

# Cursor Subagent

Use Cursor Agent as a one-shot, read-only reviewer. Cursor runs in the command's
working directory, so it can inspect that workspace directly.

Cursor may delegate bounded parts of the review to its own subagents when
useful. Carry this permission into the review prompt; do not add a blanket
"do not delegate" or "do everything yourself" restriction unless the user
explicitly requests it. Any further delegation inherits the same task scope
and read-only boundary. Cursor remains responsible for checking the evidence,
synthesizing the findings, and identifying unresolved gaps in its final response.
Judge the result by its evidence and coverage, not by whether subagents were
used. A child failure matters when it leaves an unresolved gap; it does not
automatically invalidate a review Cursor completes through other means.

## Run a review

1. Define one bounded, read-only review assignment. Include the goal, relevant
   paths, known constraints, expected deliverable, and non-file conversation
   context Cursor cannot infer.
2. Explicitly prohibit file and external-system changes and pass `--mode ask`
   (or `--mode plan` when the requested deliverable is specifically a plan).
   Ask Cursor to inspect primary artifacts and return findings, evidence,
   disagreements, or a recommendation for Codex to verify and synthesize.
3. Put the prompt in a scratch file outside the repository. Invoke the
   `scripts/cursor-subagent` helper beside this `SKILL.md` from the target
   working directory, piping the prompt on stdin. The helper runs Cursor Agent
   in non-interactive print mode. Use `--effort high` by default and pass
   `--effort xhigh` for difficult tasks. The helper maps these tiers to the
   matching pinned Cursor GPT-5.6 Sol models.
4. On macOS, Cursor Agent reads its login from Keychain. If the command runner
   uses a sandbox that blocks Keychain, invoke the helper with that runner's
   narrowly scoped unsandboxed/elevated execution option from the outset. Scope
   any persistent approval to the helper path, not to a shell or `cursor-agent`
   generally. `SecItemCopyMatching failed -50` followed by exit 139 means the
   execution context blocked Keychain; retry the same read-only call once
   outside that sandbox. It does not by itself mean the login or model is bad.
5. Start one call and wait on that same process. If the command tool yields a
   running-session identifier, resume that process; do not submit a duplicate
   merely because Cursor has not produced output yet.
6. Treat stdout as Cursor's response and judge success by the exit code. A zero
   exit with non-empty stdout is a completed call. On a non-zero exit, report
   the failure and inspect the workspace before deciding whether a retry is
   safe. A failed delegation may be retried at most twice, for no more than
   three attempts total. Each retry must follow that inspection; never retry
   blindly after a task that may have changed files or external state.
   The helper normally captures Cursor's partial event stream. If Cursor emits
   a complete final response and then exits with `WritableIterable is closed`,
   the helper recovers that response and exits zero; this is a completed call,
   not a retry case. A non-zero exit means no complete response was recoverable.

Example command shape:

```bash
"${CODEX_HOME:-$HOME/.codex}/skills/cursor-subagent/scripts/cursor-subagent" --effort high --mode ask < /tmp/cursor-subagent-prompt.md
```

Pass ordinary Cursor CLI flags after the helper name when useful, such as
`--output-format json` or `--trust`. Always pass `--effort high` or `xhigh` as
described above. Use `--trust` only after confirming the current workspace is
one the user intends Cursor to access. Do not pass `--force`, `--yolo`, or
`--approve-mcps` unless the user has explicitly authorized the broader effect
and it is necessary for the delegated task.

By default, the helper uses Cursor's `stream-json` partial-output mode
internally but returns only the final plain-text response. Explicitly passing
`--output-format` or `--stream-partial-output` disables this recovery layer and
passes Cursor's requested output through unchanged.

## Model choice

The helper maps `high` and `xhigh` to `gpt-5.6-sol-high` and
`gpt-5.6-sol-xhigh`. GPT-5.6 Sol is a strong reasoning model reached through
Cursor, distinct from the Claude subagent and stronger than the previously
pinned Grok model. High is the default balance; Extra High is for difficult
problems such as ambiguous root-cause investigations, consequential reviews, or
complex long-horizon work. Pinning the model prevents Cursor's Auto router from
silently changing models.

Model availability is account- and time-dependent. If Cursor rejects the pinned
ID, run `cursor-agent models`, report that the configured model is unavailable,
and ask before changing the skill's default. Do not silently fall back to Auto.

## Safety and verification

The helper marks the launched Cursor process with a recursion sentinel. If
Cursor tries to invoke `claude-subagent`, `cursor-subagent`, or `dual-subagent`,
that nested helper exits 126. Cursor may still use its own native subagents
within the inherited read-only scope.

Cursor's plain `--print` mode can use write and shell tools. This skill always
uses a read-only mode: keep Cursor inside the current task, do not pass secrets
unnecessarily, and never use Cursor as the writer, implementer, or
external-system operator through this skill.

After Cursor returns, verify consequential claims and inspect any changes or
tests yourself. Present Cursor's result as a delegated contribution, not as
independently confirmed fact.
