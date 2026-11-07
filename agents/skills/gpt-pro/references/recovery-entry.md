## Recovery and other operations

- If the caller dies or exits 124/255, reattach with `gpt-pro --run-id <literal-id>`
  in the same background envelope. This waits on a live worker, or restores collection
  from the saved original conversation URL if the worker died. Recovery never resends
  the initial prompt. Explicitly queued supplements keep their separate send/receipt
  lifecycle; normal completion checks, model audit, and browser cleanup still apply.
  Without a usable saved URL, it exits 6; inspect the artifacts and report the failure.
  A post-send error whose stderr says `recoverable: true` restores the same way:
  the answer may already be finished in the original conversation.
  Empty output without a completion event means the call may still be running.
- To stop generation, use `gpt-pro --stop <literal-id>`. `TaskStop` or `kill` on a
  background task can kill its detached collector while browser generation continues.
  To end only the wait, let `--max-wait` expire or detach from the harness; preserve
  the collector and do not kill the process tree. Reattach with `--run-id` afterward.
- For any failure, read [Runtime, recovery, and diagnostics](operations.md#if-it-fails)
  before choosing a retry. Ambiguous or post-send failures must not trigger a blind
  resubmit; a fresh quota-consuming run after a terminal failure requires the user’s decision.
- For changing timeouts, diagnosing queues, stopping a run, or retrieving artifacts,
  read the relevant section of [Runtime, recovery, and diagnostics](operations.md).
  Browser teardown is operator maintenance, not routine recovery.

