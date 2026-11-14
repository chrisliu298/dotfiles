## Control and failure semantics

- `send` returns JSON with `delivery`. `carbon`/`hydro` `confirmed` means steering activation
  or transcript receipt was confirmed, not that the message has joined the turn yet
  (steering waits for the next safe boundary, as on the other backends); `pro`
  `confirmed` means the relay acknowledged delivery into the running answer.
  `claude`/`gpt`/`ark` `submitted` means text was pasted and Enter sent; it
  does not independently prove consumption or task completion. Use `wait` for the
  resulting reply. Do not interrupt merely to add context.
- A `pro` conversation accepts no follow-up once its answer finishes: `send` fails
  and says to start a new task that includes the answer and the new question.
- `carbon`, `hydro` and `pro` `unconfirmed` return 124; the message may still be queued. Inspect it or
  keep waiting, without automatically resending or restarting.
- A failed `send` leaves that session's latest request failed. `wait` reports the
  failure instead of returning its previous reply; a subsequent successful send
  clears it. In a batch, retain failed delivery entries separately from completed
  replies. Do not treat them as answers to the supplement.
- `wait SESSION [SESSION ...] --timeout N` defaults to 3600 seconds per session,
  7200 for `pro`.
  Timeout returns 124 when all failures are timeouts; mixed failures return 1.
  Multi-session replies retain individual exit codes and diagnostics.
- For `carbon` and `hydro`, `wait` resumes a turn that ended in a transient network or
  provider error by sending a continuation itself, at most twice per request, and
  notes each on stderr. Do not also send "continue"; a failure it reports already
  used those attempts.
- `status` and `capture` are diagnostic. `input_ready=1` does not prove the model
  is idle. `interrupt` requests an urgent stop using the backend's native key;
  it does not guarantee background work was cancelled. Inspect before new work.
  Interrupting `pro` stops its run for good.
- `list` includes sessions started by earlier entrypoints. Session actions do not
  require the backend to remain available, so cleanup is still possible.

On failure, inspect output/pane and the workspace before a safe retry. Allow at
most two retries, never duplicate a running request or a message that may already
be queued. Stop every session you started before the final answer; keep one only
when follow-ups are needed and explicitly name it as open. Stop only named sessions,
never the tmux server.

Nonzero exits and empty replies from either `wait` or `--once` are failures. The helper never changes login,
installs missing dependencies, chooses a replacement backend, or merges the reviews
itself; the calling agent performs verification and synthesis.
