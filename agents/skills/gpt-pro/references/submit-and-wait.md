## Invoke and wait

An authorized invocation is the go-ahead; do not add a runtime confirmation.
Runs usually take 5–20 minutes and can take 1–2 hours including waiting.
Launch once in the background with the Bash tool:

```text
command:           gpt-pro < question.md
run_in_background: true
timeout:           7260000
```

Claude Code notifies you when it exits. If the tool merges stdout and stderr,
`run_id=` appears early and may be absent from the final chunk, so record the
literal run ID as soon as it appears. Continue independent work meanwhile. Do not
start another waiter or polling loop, or submit again, while the call is live.
Finish collecting the wrapper's output before ending your turn when possible; if
interrupted, recover with the run ID as described below.

The answer goes to stdout; `run_id=<id>`, `recover_with=…`, and diagnostics go to
stderr. Keep these streams separate if saving them. Capture the literal run ID for
recovery. If `gpt-pro` is not on PATH, use `<this-skill-dir>/scripts/gpt-pro`.

