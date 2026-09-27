---
name: gpt-subagent
description: Obtain an independent read-only review or second opinion from Codex CLI. Use when the user asks to ask GPT, get a GPT take, or use GPT as a reviewer. Defaults to persistent tmux with follow-ups and interruption; supports explicit one-shot mode. Not for delegated implementation or external operations.
---

# GPT Subagent

Use Codex CLI as a read-only reviewer from Claude. Both review skills use the
same session manager at `../review-subagent-shared/review-subagent`; only their
harness adapters and pinned models differ. Model is pinned to `gpt-6-astra`. Reasoning effort is fixed to
`high`. The helper runs in the current working directory using the user's
existing login. Do not install software or change credentials during a review.

## Default: persistent tmux review

1. Define one bounded read-only assignment, including the goal, relevant paths,
   constraints, expected deliverable, and conversation context the reviewer lacks.
   Explicitly prohibit file changes and external-system changes.
2. Write the prompt to a scratch file outside the repository. Run the helper
   beside this skill from the target workspace. With no arguments (or `start`),
   it creates a detached tmux session and prints its unique name:

   ```bash
   helper="$HOME/.claude/skills/gpt-subagent/scripts/gpt-subagent"
   session="$($helper < /tmp/review-prompt.md)"
   $helper status "$session"
   $helper capture "$session"
   $helper send "$session" < /tmp/review-followup.md
   $helper interrupt "$session"
   $helper list
   $helper stop "$session"
   # Optional human interaction: tmux attach -t "$session"
   ```

3. Follow that same session until it returns a substantive result. A printed
   session name means startup was dispatched, not that the review succeeded.
   `capture` includes 300 lines of history plus the visible screen. `status`
   reports the pane, whether it exited, its exit code if available, and whether
   bracketed paste is enabled (`input_ready=1`). That flag does not mean the
   model is idle or that trust/onboarding prompts have been resolved. Inspect
   the pane before sending work; report startup blockers without approving them
   automatically.
4. `send` pastes stdin and presses Enter. Input sent while busy may be queued.
   For a direction change, use `interrupt` (Escape), inspect the pane to confirm
   the model turn stopped, then send the correction and wait for acknowledgement.
   Escape does not guarantee cancellation of commands the harness has already
   moved to the background; inspect those separately before relying on a stop.
5. Inspect the final response and verify consequential claims against primary
   artifacts. An interactive session normally stays alive after a response;
   idle or dead pane state alone is not proof of a successful review. Exited
   panes are retained for diagnosis. Stop only the named review session when
   finished; never kill the tmux server or unrelated sessions.

The `scripts/gpt-subagent-tmux` entrypoint is an alias with the same interface.
Initial tmux prompts are limited to 128 KiB; send further context as follow-ups.
Both helpers require tmux in this mode. Do not switch models or effort through
interactive slash commands: the selected model/high combination is fixed for
this workflow.

## Explicit one-shot mode

For a bounded request that needs no persistent session:

```bash
$helper --once < /tmp/review-prompt.md
$helper --once --output-format json < /tmp/review-prompt.md
```

Both helpers accept `--once`, `start`, `list`, `capture`, `status`, `send`,
`interrupt`, and `stop`. `start` and `--once` optionally accept `--model` with
only their pinned model and `--effort high`; other values and raw harness flags
are rejected. The assignment is always supplied on stdin.

One-shot mode returns final response text on stdout and diagnostics on stderr.
JSON output requires `jq` and uses the same envelope for both harnesses:
`{"result":"...","exit_code":0,"is_error":false}`. A nonzero exit or an empty
response is failure. Session history is not persisted in one-shot mode. Wait on
the same process if the command tool yields a running-session ID; do not start
another request because output has not arrived. JSON is a shared wrapper format,
not a harness-specific event stream.

## Scope, delegation, and failures

The reviewer may use its native subagents for bounded parts of the review when
useful. Carry that permission and the same read-only scope into the assignment;
do not require delegation or prohibit it unless the user says so. The reviewer
owns evidence checking and synthesis. A child failure matters only when it
leaves an unresolved gap.

The shared `CODEX_REVIEW_SUBAGENT_ACTIVE` sentinel blocks nested review helper
calls (including the Claude/GPT/Cursor/dual helpers) with exit 126. Native
subagents remain available. Never use this skill for implementation or external
operations; use the caller's native agents for delegated execution.

Both workflows prohibit writes in the assignment. Harness enforcement differs:
Claude uses the existing `c` launcher (which bypasses permission prompts), while
Codex uses a read-only shell sandbox and `approval=never`. Neither establishes
read-only enforcement for every external tool. Keep the reviewer within the
user's authorized scope and avoid passing unnecessary secrets.

Judge results by actual responses and exit status, not diagnostic text alone.
On failure, inspect the pane/output and workspace, report the error, then retry
only if safe. Allow at most two retries, never duplicate a running request.
Attribute the contribution, verify consequential findings, and report gaps.
