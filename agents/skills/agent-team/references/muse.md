# Muse backend

Uses Muse Code (`muse` on PATH) with the existing Meta login. Model is pinned to
`muse-wonder-full-1.0` and effort to `high`, Muse Code's own default for it; Meta
publishes no guidance that `xhigh` improves this model for review work. Report a
missing CLI or an unavailable model; do not log in or choose another model.

Runs like the user's `m` launcher (`--yolo`): no approval prompts, no sandbox,
network available, and the launch directory trusted for the run. Approvals must
stay off: an unattended approval request, including one raised under a permission
profile such as `:read-only`, stalls the turn until `wait` times out. Read-only
scope is an assignment instruction, not a permission boundary.

`Stop` and `StopFailure` hooks passed through `-c hooks=...` record each finished
or failed turn; `wait` reports a failed turn as an error. Muse runs hooks with a
scrubbed environment, so the hook command carries the turn directory itself.

`send` pastes the message and presses Enter; `submitted` does not prove
consumption. Input sent during a turn is queued: Muse steers it into the running
turn or runs it as its own turn afterwards. `wait` returns only once Muse is idle
with nothing queued, so the reply covers the latest message either way.
`interrupt` sends Escape, which cancels the turn without a finished-turn record
and restores it plus any queued input as one draft; the helper clears that draft
so the next `send` is not appended to it. Interrupted work is not retried.

One-shot mode runs `muse exec` without a session log, passing the prompt as an
argument because `exec` does not read stdin.
