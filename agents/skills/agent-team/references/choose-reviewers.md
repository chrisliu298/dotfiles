## Choose reviewers

Read the user's message for backend names and assignments:

- “让 Claude 审查” → `claude`.
- “Claude 和 Cursor 并行独立审查” → `claude` and `cursor`, same assignment.
- “GPT、Claude、Cursor、Muse、DeepSeek 都看一下” → `gpt`, `claude`, `cursor`, `muse`
  and `ds`, same assignment.
- “也问问 Pro” / “ChatGPT Pro” alongside other backends → `pro`.
- “Claude 看正确性，GPT 看测试” → `claude` and `gpt`, distinct assignments.

Each backend runs at most once per call; a repeated `--backend` is rejected. When
the user asks for more reviewers than distinct backends, say so and ask how to
split the work. Start every reviewer with one `start` call: backends without a
file share the stdin prompt, and `--backend NAME=FILE` gives a backend its own
assignment (an absolute path or one relative to the working directory). Write one backend-neutral prompt; the helper adds
each backend's completion and launch details, so do not tailor prompts per
backend or add deadlines (`wait --timeout` bounds the wait). `--file PATH`
(repeatable) shares local files: `pro` cannot open paths, so its prompt inlines
their contents, while the other backends receive the absolute paths to read.
If no backend was chosen and the request does not identify one, ask which to use.
These backends are separate CLI sessions, not the caller's native subagents (the
Agent tool). A request for a “subagent” or “subagent review” that names no backend
uses the native subagent workflow, not this skill.
Always name backends by these ids, in prompts, reports and attribution alike:
`gpt` is Codex CLI; `claude` is Claude Code; `cursor` is Cursor Agent on Gemini;
`muse` is Muse Code; `ds` is DeepSeek through Claude Code; `pro` is ChatGPT Pro
through the gpt-pro relay. Product names describe only the underlying tool.

Before dispatch, read only the references for the chosen backends:
[`gpt`](gpt.md), [`claude`](claude.md), [`cursor`](cursor.md),
[`muse`](muse.md), [`ds`](ds.md), [`pro`](pro.md).
Use `scripts/agent-team` beside this `SKILL.md`; resolve its actual installed
location rather than assuming a particular agent's skill directory. It requires
Node.js and zsh, plus tmux for persistent sessions other than `pro`. `backends` reports configured
availability, not a verified login or model entitlement. This skill is installed
for Claude Code only. Report unavailable backends; do not substitute one.

