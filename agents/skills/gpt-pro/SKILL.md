---
effort: low
name: gpt-pro
description: |
  Send a prompt to ChatGPT Pro when the user requests GPT-Pro, a Pro take,
  or a second opinion from ChatGPT Pro.
allowed-tools: Bash(gpt-pro:*), Bash(${CLAUDE_SKILL_DIR}/scripts/gpt-pro:*), Bash(ssh:*), Read, Write
user-invocable: true
---

# gpt-pro

Send one self-contained prompt through `gpt-pro` and return its verified answer.
The engine runs on this Mac by default (`GPT_PRO_HOST=<ssh-host>` relays to a remote
one instead). The wrapper chooses local or SSH transport, submits once, and waits through
network drops. Each new prompt starts a fresh ChatGPT conversation; `--run-id`
reattaches to the original one.

## Prepare the prompt

Put the question and relevant session decisions in a file. GPT-Pro cannot see this
conversation or local files; attach needed files with `-f <path>` rather than
hand-concatenating them. The wrapper validates, secret-scans, and caps composed input
at 5 MB before submission. Use only context authorized for this request.

```bash
gpt-pro -f src/foo.py -f src/bar.py < question.md
```

- For attachment flags, directory inputs, dry runs, PATH failures, or large-paste
  handling, read [Invocation and attachments](references/attachments.md).
- When the answer depends on external facts, use the grounding guidance in
  [Conditional prompt guidance](references/prompting.md#grounding-external-facts).
- For judgments, design advice, and second opinions, use that reference's
  [calibration block](references/prompting.md#calibration-block); skip it for
  deterministic lookups and mechanical transforms.

## Invoke and wait

An authorized invocation is the go-ahead; do not add a runtime confirmation.
Runs usually take 5–20 minutes and can take 1–2 hours including waiting.
Launch once using the harness's background execution facility. With a Bash tool
that supports these fields, use:

```text
command:           gpt-pro < question.md
run_in_background: true
timeout:           7260000
```

Claude Code notifies you when it exits. On other harnesses, allow 121 minutes for
the wrapper's default 120-minute deadline and do not invent unsupported tool
arguments; per-call yield or wait limits (such as `yield_time_ms`) bound one
collection call, not the command's lifetime. Choose how to collect the result
using the caller's available tools:

- With async `functions.exec` and `notify()`, await `exec_command` running
  `gpt-pro` inside the script. If it returns a running-session ID, await
  `write_stdin` on that same process until it exits, then call `notify()` with
  the exit code and collected output. Let the script yield while you do
  independent work; keep the awaited script alive until notification.
  Unawaited promises are discarded when the script ends. This bridges completion
  into the current turn; do not assume it wakes a finished turn.
- With ordinary shell tools, collect the same process's result using
  `write_stdin` (or the tool's equivalent). A running-session ID alone does not
  promise a completion notification.

If the tool merges stdout and stderr, accumulate every chunk, including the first:
`run_id=` appears early and may be absent from the final chunk. Record the literal
run ID as soon as it appears. Repeated `write_stdin` calls on that one session are
collection, not polling; `functions.wait` collects the yielded script rather than
adding a waiter. Continue independent work meanwhile. Do not start another waiter
or polling loop, or submit again, while the call is live. Finish collecting the
wrapper's output before ending your turn when possible; if interrupted, recover
with the run ID as described below.

The answer goes to stdout; `run_id=<id>`, `recover_with=…`, and diagnostics go to
stderr. Keep these streams separate if saving them. Capture the literal run ID for
recovery. If `gpt-pro` is not on PATH, use `<this-skill-dir>/scripts/gpt-pro`.

## Verify the result

Use a non-empty successful response. When retrieving artifacts directly, read
`result.json` first: only `status: "ok"` makes `response.md` usable. Rejected,
incomplete, partial, and pending bodies are diagnostics, even if they read like
finished answers. Report model-audit uncertainty when it affects reliance on the result.
Verify relevant external claims before relying on them; use the conditional prompt
reference for grounding and judgment checks.

## Recovery and other operations

- If the caller dies or exits 124/255, reattach with `gpt-pro --run-id <literal-id>`
  in the same background envelope. This waits on a live worker, or restores collection
  from the saved original conversation URL if the worker died. Recovery never submits
  again and finishes with the normal completion checks, model audit, and browser cleanup.
  Without a usable saved URL, it exits 6; inspect the artifacts and report the failure.
  Empty output without a completion event means the call may still be running.
- To stop generation, use `gpt-pro --stop <literal-id>`. `TaskStop` or `kill` on a
  background task can kill its detached collector while browser generation continues.
  To end only the wait, let `--max-wait` expire or detach from the harness; preserve
  the collector and do not kill the process tree. Reattach with `--run-id` afterward.
- For any failure, read [Runtime, recovery, and diagnostics](references/operations.md#if-it-fails)
  before choosing a retry. Ambiguous or post-send failures must not trigger a blind
  resubmit; a fresh quota-consuming run after a terminal failure requires the user’s decision.
- For changing timeouts, diagnosing queues, stopping a run, or retrieving artifacts,
  read the relevant section of [Runtime, recovery, and diagnostics](references/operations.md).
  Browser teardown is operator maintenance, not routine recovery.

For a follow-up, include the prior answer and new question in a new prompt; the
relay does not carry conversation context between calls.
