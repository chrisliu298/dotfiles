# `claude` backend

Uses Claude Code through the configured `c` function in the user's `.functions`.
Model is pinned to `opus`, effort to `high`, with the existing login. Do not change
the selected model/effort through slash commands or alter credentials during review.

The launcher bypasses permission prompts. Read-only scope is an instruction,
not an operating-system sandbox: prohibit file and external-system changes in
the assignment and verify consequential claims yourself.

The native Stop hook records finished turns for `wait`. `send` can submit text
while the turn is running; it may be queued. `submitted` does not prove that the
message has already influenced the active turn. Use `wait` and inspect the reply
for incorporation. `interrupt` sends Escape; already-backgrounded work may survive.

The helper answers Claude Code's workspace trust dialog for the launch directory,
as `cursor` and `muse` trust theirs; a dialog still showing after 10 seconds fails
`wait`. If any other startup or permission prompt blocks work, inspect `capture`
and report the blocker without approving broader access automatically. One-shot
mode uses `--no-session-persistence`.
