# Pro backend

Uses ChatGPT Pro through the gpt-pro skill's wrapper (`GPT_PRO_BIN`, else
`gpt-pro` on PATH, else the gpt-pro skill installed beside this one) and its
existing relay login. Report a missing wrapper or a relay failure; do not log in,
reconfigure the relay, or fall back to another backend. Each run spends Pro quota.

No tmux: the relay's detached worker owns the run, and the session handle is
`pro-review-<run_id>`. `start` submits and returns once the run id is known;
`wait` reattaches to the run (recovering collection if the worker died) and never
resubmits. A timed-out `wait` leaves the run going, so wait on the same handle again.

Pro cannot read local paths. `--file` inlines each file through the wrapper's
`-f`, which secret-scans and caps the composed prompt before any quota is spent.

`send` delivers a supplement into the running answer with a message id derived
from the run and text, so retrying the identical supplement is not sent twice.
Before Pro starts answering, `send` fails as not ready; resend the same text shortly.
Once the answer has finished the conversation accepts nothing further; start a
new task that includes that answer and the new question.

`interrupt` and `stop` both stop the run, which cannot resume. `status` reports
`running`, `finished`, `stopped`, or a failure; `capture` adds the local engine's
recent progress trace when the relay runs on this host.
