## Supplement a running request

When the user asks to add information while Pro is working, send it to the
original run instead of starting a fresh conversation:

```bash
gpt-pro --send <literal-run-id> --message-id <stable-message-id> < supplement.md
```

The existing `-f` attachment flags also work with `--send`. Send returns a
delivery receipt on stderr, not an answer on stdout. `sent` proves the new user
message appeared in the original conversation; `queued` or exit 124 is pending.
The default receipt wait is 30s (`--max-wait` changes it). Preserve the printed
message ID: every retry must use the SAME ID and identical composed content.
Never retry by omitting the ID or generating a fresh one. Resume collecting the
original invocation; its final answer includes the supplements. If its collector
has died, restore it with `--run-id` before retrying the same supplement.

New supplements are accepted only while the original worker is active and has
reached the post-send monitor. Finished/finalizing/stopping runs reject them, as
do old workers that lack this feature. After a run has finished, include its
answer and the follow-up question in a new prompt.
