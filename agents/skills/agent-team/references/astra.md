# `astra` backend

It is the [`sol`](sol.md) backend launched through `~/.local/bin/codex-ark` instead of the
subscription login: the same Codex CLI (0.159.2+), `~/.codex` sessions, `--yolo`-equivalent full
access, `--effort` handling, turn detection, `wait`, `send`, `interrupt` and one-shot behavior, so
read `sol.md` for those.

The model is pinned to GPT-6.2-Astra on Ark; the helper always launches with `ARK_MODEL=astra`, so
the caller's `ARK_MODEL` has no effect. Each session's Ark tracing label is its session name
(`agent-team-astra` for one-shot calls). Sessions started as `ark-review-*` under the former
backend name are `astra` sessions.

`backends` reports `astra` unavailable when `codex-ark` or `ARK_API_KEY`, `ARK_OPERATOR_ID`
and `ARK_OPERATOR_EMAIL` (from `~/.zshenv.local`) are missing. A `429 Too Many Requests` is
the endpoint's rate limit: report it; do not retry in a loop or switch to `sol` unless the user
asks.
