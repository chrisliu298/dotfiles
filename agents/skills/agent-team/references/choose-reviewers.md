## Choose reviewers

The fixed form `/agent-team ID ID ...` names the backends directly.
Its `ID:` lines become per-backend files (`--backend ID=FILE`), each holding that line's text
plus the shared text; the shared text alone goes on stdin for the rest.
Otherwise read the user's message for backend names and assignments:

- “让 Claude 审查” → `claude`.
- “Claude 和 Carbon 并行独立审查” → `claude` and `carbon`, same assignment.
- “GPT、Claude、Neon 都看一下” → `sol`, `claude` and `neon`, same assignment.
- “Gemini” or “Cursor” alone names no backend: ask whether `carbon`, `neon` or both.
  `cursor` was carbon's former name and is no longer accepted.
- “也问问 Pro” / “ChatGPT Pro” → not available to agents: say so, and run the other named
  backends without a stand-in for it.
- “Claude 看正确性，GPT 看测试” → `claude` and `sol`, distinct assignments.
- “用方舟的 GPT 看一下” / “gpt astra 方舟” / “Astra” / “ark” → `astra` alone. Sol runs only on
  the subscription (`sol`); for “方舟 Sol”, ask whether `sol` or `astra`.
- “gpt, carbon, claude, 用方舟 gpt astra” → `astra`, `carbon` and `claude`: the qualifier moves
  the one GPT slot to Ark.
- No backend named (“让 agent-team 看看”) → the rule of thumb in SKILL.md, by difficulty.

GPT has one slot. When the user's backend choice qualifies GPT or Codex with 方舟, Ark or Astra
(Astra exists only on Ark), that slot is `astra` and never also `sol`; count it once when telling
the user how many backends run. Choose both only when the user asks for the subscription and Ark
side by side. Plain “GPT” or “Codex” with no
such qualifier is `sol` on the subscription; never substitute one for the other. 方舟 in the task
content (for example a project's Gemini endpoints) does not choose a backend.

Each backend runs at most once per call; a repeated `--backend` is rejected. When
the user asks for more reviewers than distinct backends, say so and ask how to
split the work. Start every reviewer with one `start` call: backends without a
file share the stdin prompt, and `--backend NAME=FILE` gives a backend its own
assignment (an absolute path or one relative to the working directory). Write one backend-neutral prompt; the helper adds
each backend's completion and launch details, so do not tailor prompts per
backend or add deadlines (`wait --timeout` bounds the wait). One `--effort` applies to every
backend in the call; when backends need different tiers, start them in separate calls. `--file PATH`
(repeatable) shares local files: the backends receive the absolute paths to read.
These backends are separate CLI sessions, not the caller's native subagents. A request for a “subagent” or “subagent review” that names no backend
uses the native subagent workflow, not this skill.
Always name backends by these ids, in prompts, reports and attribution alike:
`astra` is Codex CLI on Ark through `codex-ark`; `sol` is Codex CLI on the subscription; `claude` is Claude Code; `carbon` and `neon` are Cursor Agent on Gemini 4 Carbon and Gemini 4 Neon.
Product names describe only the underlying tool.

Before dispatch, read only the references for the chosen backends:
[`astra`](astra.md), [`sol`](sol.md), [`claude`](claude.md), [`carbon` and `neon`](cursor.md).
Use `scripts/agent-team` beside this `SKILL.md`; resolve its actual installed
location rather than assuming a particular agent's skill directory. It requires
Node.js and zsh, plus tmux for persistent sessions. `backends` reports configured
availability, not a verified login or model entitlement. This skill is installed
for Claude Code and agy. Report unavailable backends; do not substitute one.

