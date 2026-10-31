# `gpt` backend

Uses the managed Codex CLI at `~/.local/bin/codex`, requiring version 0.159.2+.
Model is pinned to `gpt-6-astra`, effort to `high`, with the existing login. Report
a missing/old CLI; do not install or silently choose another model during review.

Runs like the user's `x` launcher (`--yolo`): approvals and the sandbox are
bypassed, so network and SSH work. Read-only scope is an assignment instruction.
Native `notify` and the primary rollout record the completed turn; title and
subagent responses must not count as the parent review. `wait` returns every
final answer in that turn, including the response after a mid-turn supplement.
`capture` can truncate or still be rendering; use `wait` for the full reply.

Native running-turn input is steered into the turn. The wrapper's `submitted`
status confirms the input submission, not an independent consumption receipt.
`interrupt` sends Escape; background work may survive. One-shot mode is ephemeral.
