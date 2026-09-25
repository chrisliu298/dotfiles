---
name: claude-subagent
description: |
  Obtain an independent read-only review from Claude Code. Use when the user
  asks to "ask Claude", "use Claude as a reviewer", get a "Claude take", or
  obtain an independent Claude review or second opinion. Do not use this skill
  to implement, complete, advance, or operate a task; use Codex's native
  subagents when delegated execution is requested.
metadata:
  surfaces:
    - codex
---

# Claude Subagent

Use Claude Code as a one-shot, read-only reviewer. Claude runs in the command's
working directory, so it can inspect that workspace directly.

Claude may delegate bounded parts of the review to its own subagents when
useful. Carry this permission into the review prompt; do not add a blanket
"do not delegate" or "do everything yourself" restriction unless the user
explicitly requests it. Any further delegation inherits the same task scope
and read-only boundary. Claude remains responsible for checking the evidence,
synthesizing the findings, and identifying unresolved gaps in its final response.
Judge the result by its evidence and coverage, not by whether subagents were
used. A child failure matters when it leaves an unresolved gap; it does not
automatically invalidate a review Claude completes through other means.

## Run a review

1. Define one bounded, read-only review assignment. Include the goal, relevant
   paths, known constraints, expected deliverable, and non-file conversation
   context Claude cannot infer.
2. Explicitly prohibit file changes and external-system changes. Ask Claude to
   inspect primary artifacts and return findings, evidence, disagreements, or a
   recommendation for Codex to verify and synthesize.
3. Put the prompt in a scratch file outside the repository. Invoke the
   `scripts/claude-subagent` helper beside this `SKILL.md` from the target
   working directory, piping the prompt on stdin. The helper runs the user's
   existing `c` function in non-interactive print mode. Always pass an effort:
   use `--effort high` by default, and use `--effort xhigh` for difficult
   problems. Do not use other effort levels.
4. Start one call and wait on that same process. If the command tool yields a
   running-session identifier, resume that session; do not submit a duplicate
   merely because Claude has not produced output yet.
5. Treat **stdout** as Claude's response and judge success by the **exit code**,
   not by anything on stderr. A zero exit with non-empty stdout is a completed
   call. On a non-zero exit, report the failure and inspect the workspace before
   deciding whether a retry is safe. A failed delegation may be retried at most
   twice, for no more than three attempts total. Each retry must follow that
   inspection; never retry blindly after a task that may have changed files or
   external state. Count an attempt as failed only after the process exits
   non-zero or exits without a response on stdout. The `unrecognized_model`
   stderr diagnostic described below is not a failed attempt and must not
   trigger a retry; keep waiting on the same process.

## The `unrecognized_model` stderr line is NOT a failure

The relay drives a private model id (`model_hub/es1_orange_o48`) that the Claude
CLI doesn't have in its built-in table, so it prints one diagnostic line to
**stderr**:

```
[claude-code:unrecognized_model] {"model":"model_hub/es1_orange_o48","query_source":"generate_session_title"}
```

This is cosmetic and expected. The real request still goes out and returns
normally — `query_source` is usually `generate_session_title` (the title
side-channel, not your task). It cannot be silenced via `modelOverrides` (that
mapping only accepts real Anthropic model ids and ignores unknown keys), so do
not chase it. Never treat this line, or any stderr text, as proof the request
failed, and never conclude "no review body" from it — read stdout.

To avoid parsing stderr entirely, capture the two streams separately, or ask for
structured output and read the `result` field only when `is_error` is `false`:

```bash
claude-subagent < /tmp/claude-subagent-prompt.md >/tmp/out.txt 2>/tmp/err.txt   # body in out.txt
claude-subagent --output-format json < /tmp/claude-subagent-prompt.md           # {"is_error":false,...,"result":"..."}
```

The helper already pins a 1M context window, so long prompts and large
repository context are fine.

Example command shape:

```bash
"${CODEX_HOME:-$HOME/.codex}/skills/claude-subagent/scripts/claude-subagent" --effort high < /tmp/claude-subagent-prompt.md
```

Pass ordinary Claude CLI flags after the helper name when useful, for example
`--model opus`, `--tools ""`, or `--output-format json`. Always pass either
`--effort high` or `--effort xhigh` as described above.

## Safety and verification

The helper marks the launched Claude process with a recursion sentinel. If
Claude tries to invoke `claude-subagent`, `cursor-subagent`, or `dual-subagent`,
that nested helper exits 126. Claude may still use its own native subagents
within the inherited read-only scope.

The helper deliberately inherits `c`'s `--dangerously-skip-permissions`. This
does not broaden the user's authorization: keep Claude inside the current task,
do not pass secrets unnecessarily, and always state the read-only boundary in
the prompt. Never use Claude as the writer, implementer, or external-system
operator through this skill, even though the underlying helper has those
technical capabilities.

After Claude returns, verify consequential claims and inspect any changes or
tests yourself. Present Claude's result as a delegated contribution, not as
independently confirmed fact.
