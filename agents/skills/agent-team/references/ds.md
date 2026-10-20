# `ds` backend

Uses Claude Code on DeepSeek's Anthropic endpoint through the configured `ds`
function in the user's `.functions`, which reads `DEEPSEEK_API_KEY` from
`~/.zshenv.local`. Model is pinned to `deepseek-flash[1m]` (every tier on
`deepseek-flash`), effort to `high`; DeepSeek maps `xhigh` to `high`, so raising
it would change nothing. Report a missing launcher or key; do not change the
model, effort, or credentials during review.

Everything else matches the [`claude` backend](claude.md): the launcher bypasses
permission prompts, the native Stop hook records finished turns for `wait`,
`send` returns `submitted`, `interrupt` sends Escape, and one-shot mode uses
`--no-session-persistence`. Read-only scope is an assignment instruction, not a
sandbox.
