# `ark` backend

Use only when the user names Ark (方舟). It is the [`gpt`](gpt.md) backend launched through
`~/.local/bin/codex-ark` instead of the subscription login: the same Codex CLI (0.159.2+),
`~/.codex` sessions, `--yolo`-equivalent full access, effort `high`, turn detection, `wait`,
`send`, `interrupt` and one-shot behavior, so read `gpt.md` for those.

The model is GPT-6-Astra on Ark. When the user asks for Sol, run the helper with
`ARK_MODEL=sol` in its environment (for example `ARK_MODEL=sol agent-team start --backend ark`);
any other value is rejected. A persistent session keeps the model it started with. Each
session's Ark tracing label is its session name (`agent-team-ark` for one-shot calls).

`backends` reports `ark` unavailable when `codex-ark` or `ARC_API_KEY`, `ARK_OPERATOR_ID`
and `ARK_OPERATOR_EMAIL` (from `~/.zshenv.local`) are missing. A `429 Too Many Requests` is
the endpoint's rate limit: report it; do not retry in a loop, switch to `gpt`, or switch
models unless the user asks.
