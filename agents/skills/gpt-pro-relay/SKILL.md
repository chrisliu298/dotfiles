---
effort: low
name: gpt-pro-relay
description: |
  Send a prompt to ChatGPT Pro when the user requests GPT-Pro, a Pro take,
  or a second opinion from ChatGPT Pro.
allowed-tools: Bash(gpt-pro:*), Bash(~/.codex/skills/gpt-pro-relay/scripts/gpt-pro:*), Bash(ssh:*), Read, Write
user-invocable: true
---

# gpt-pro-relay

Send one self-contained prompt through `gpt-pro` on macmini and return its verified
answer. The wrapper chooses local or SSH transport, submits once, and waits through
network drops. Each invocation starts a fresh ChatGPT conversation.

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

On other harnesses, use their supported background/session mechanism and allow
121 minutes for the wrapper's default 120-minute deadline. Do not invent unsupported
tool arguments. Continue independent work and wait using the harness's completion
mechanism; do not run a second polling loop or submit again while the call is live.

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
  in the same background envelope. This waits on the existing run without submitting
  again. Empty output without a completion event means the call may still be running.
- For any failure, read [Runtime, recovery, and diagnostics](references/operations.md#if-it-fails)
  before choosing a retry. Ambiguous or post-send failures must not trigger a blind
  resubmit; a fresh quota-consuming run after a terminal failure requires the user’s decision.
- For changing timeouts, diagnosing queues, stopping a run, or retrieving artifacts,
  read the relevant section of [Runtime, recovery, and diagnostics](references/operations.md).
  Browser teardown is operator maintenance, not routine recovery.

For a follow-up, include the prior answer and new question in a new prompt; the
relay does not carry conversation context between calls.
