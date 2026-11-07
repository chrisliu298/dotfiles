## Persistent task

Write a bounded read-only assignment to a scratch file outside the repository:
goal, relevant paths, constraints, expected deliverable, and conversation context.
The deliverable can be an analysis, a research synthesis, a proposed plan, or a
review. Preserve the user's requested task rather than turning every assignment
into a code review. For a review or an independent proposal, hand over the
artifacts (code, request, outputs, data paths) and the question, not your own
conclusion or candidate answer: a reviewer that sees your reasoning tends to
confirm it. Ask for evidence you can check against the primary artifacts
(paths, line numbers, commands and their outputs). Backend tool capabilities still limit what can be executed.
Explicitly prohibit file and external-system changes. Native reviewer subagents
may handle bounded parts under the same scope unless the user says otherwise.
The reviewer owns its evidence and synthesis; a child failure matters when it
leaves an unresolved coverage gap. Nested review-helper calls are blocked.

From the authorized working directory:

```bash
# helper is scripts/agent-team beside this SKILL.md.
$helper backends
session="$($helper start --backend claude < /tmp/review.md)"
# Same assignment for gpt, cursor and muse, a distinct one for claude:
$helper start --backend gpt --backend cursor --backend muse \
  --backend claude=/tmp/claude-review.md < /tmp/review.md
# pro receives the file contents; claude receives the path:
$helper start --backend pro --backend claude --file src/main.py < /tmp/review.md
$helper wait "$session"
$helper send "$session" < /tmp/supplement.md
$helper wait "$session"
$helper stop "$session"

# A multi-backend start returns a JSON manifest of independent sessions.
$helper start --backend claude --backend gpt --backend muse < /tmp/review.md
# Read session handles from the manifest; later actions infer each backend.
$helper wait "$session1" "$session2" "$session3"
$helper send "$session1" "$session2" "$session3" < /tmp/supplement.md
$helper wait "$session1" "$session2" "$session3"
$helper stop "$session1" "$session2" "$session3"
```

Single-backend start prints its session name. Multi-backend start returns
`{"sessions":[{"backend":"claude","session":"..."}],"errors":[],"is_error":false}`.
Inspect the exit code and errors. A partial startup returns nonzero while retaining
successful handles: collect those reviews and stop their sessions; do not retry the
whole batch. Startup handles are also printed to stderr as they arrive, for recovery
if the caller is interrupted. A handle proves dispatch, not a completed review.

After start and every supplement, run `wait` and collect that same waiter to
completion. If the command tool yields a running process ID, resume it instead
of launching another waiter. Use background completion notification when the
caller supports it; otherwise await the process while doing independent work.
Completion notification applies to the active caller turn, not a finished one.

`wait` returns the full reply, including backend/session attribution for multiple
sessions. Never use a quiet screen or `capture` as proof of completion. A finished
turn still needs the requested findings and deliverable; an opener is unfinished
work. Continue the same session with a focused request to finish missing coverage.
Verify consequential claims against primary artifacts and produce the requested
deliverable. For multiple contributors, preserve attribution and identify relevant
agreements, disagreements, and remaining gaps.

