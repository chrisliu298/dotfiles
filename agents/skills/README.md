# Skills

This directory (`agents/skills/`) is the single source of truth for repo-owned **skills**, their **authoring references** (`references/`), and the manual-enabled set (`manual-skills.enabled`) — no MCP or plugin config lives here. It doubles as the catalog for all agent extensions across Claude and Codex: **skills**, **MCP servers**, and a curated set of **plugins** are all managed by `dotfiles.sh`, but only skills are stored under this path — MCP servers and plugins are defined by the `MCP_SERVERS` and `PLUGINS` tables in `dotfiles.sh`, not here.

| Type | What it does | Managed by |
|------|--------------|------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table in `dotfiles.sh` |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table in `dotfiles.sh` |
| Plugin | Bundles commands, agents, hooks, and skills | `PLUGINS` table in `dotfiles.sh` (user scope) |

## Skills

Single source of truth: own skills live in `agents/skills/`; community/third-party skills are cloned to `~/.cache/skills-src/`. Both are symlinked into per-agent skill dirs:

- Claude → `~/.claude/skills/`
- Codex  → `~/.codex/skills/`

A shared/universal `SKILL.md` is written to work across both agents; agent-specific scope is set via explicit `SKILLS` entries in `dotfiles.sh` (e.g., relay and prism are claude-only, so they never reach Codex). Claude-specific frontmatter (`allowed-tools`, `user-invocable`, `effort`) is ignored by Codex.

Toggle manual skills with `./dotfiles.sh enable/disable <name>`; list status via `./dotfiles.sh skills`.

### Skill matrix

Columns: **C**laude · Code**x**. Legend: ✓ auto-installed · ✱ manual (opt-in via `enable`) · — not wired to this agent.

> GLM, Kimi, DeepSeek, and MiMo are all reached **through** Claude Code as the harness (each is a `claude` session pointed at that model's endpoint) via the `glm`/`km`/`ds`/`mm` aliases (see `shell/.functions`), so they inherit the Claude column directly (no separate skill dir). The Claude-only orchestration skills (relay, prism, goal-loop, keep-warm, crons, codex-first, skill-creator) — plus recall, which reads Claude's own transcript store — stay off Codex; relay and prism are additionally guarded so a dispatched peer can't trigger them.

**Enabled** (✓ auto-installed):

| Skill | C | X | Source · Description |
|-------|:-:|:-:|----------------------|
| arxiv-reader            | ✓ | ✓ | local — Read arxiv via TeX / HF markdown / HTML fallback |
| claude-subagent         | — | ✓ | local — Read-only Claude review helper for Codex |
| gpt-pro-relay           | — | ✓ | local — SSH to ChatGPT Pro Extended on macmini (CLI on PATH from the Codex copy) |
| pdf                     | ✓ | ✓ | [anthropics/skills][c-pdf-a] (Claude) / [openai/skills][c-pdf-o] (Codex) — PDF read/edit |
| push                    | ✓ | ✓ | local — Push to remote (auto-picks single vs atomic commits) |
| session-history         | — | ✓ | local — Retrieve exact, redacted turns from past Codex tasks and pre-compaction history |
| skill-creator           | ✓ | — | [anthropics/skills][c-sc] — Create / edit / benchmark skills |

**Disabled** (✱ manual, opt-in via `./dotfiles.sh enable <name>`):

| Skill | C | X | Source · Description |
|-------|:-:|:-:|----------------------|
| autoresearch            | ✱ | ✱ | local — Karpathy-faithful experiment loop |
| codex-first             | ✱ | — | local — Route hands-on work to `codex exec` while Claude specs + reviews (Claude-only) |
| crons                   | ✱ | — | local — Durable manifest + re-arm for the recurring /loop cron fleet (Claude-only; preparer-not-actuator, no false assurance) |
| deslop                  | ✱ | ✱ | local — Strip AI-slop from code changes |
| goal-drive              | ✱ | ✱ | local — Drive a goal artifact (GOAL.md / checklist / phased doc) to verified done |
| goal-elicit             | ✱ | ✱ | local — Multi-round interview → verifiable Goal Contract |
| goal-loop               | ✱ | — | local — Stepped elicit→review→fix loop (composes goal-elicit/goal-drive/prism; default review is prism, Claude-only) |
| interviewer             | ✱ | ✱ | local — Mock AI/ML technical interviews |
| keep-warm               | ✱ | — | local — Cache heartbeat (uses Claude-only scheduling tools) |
| prism                   | ✱ | — | local — Multi-perspective parallel review (Claude-only caller; dispatches parallax to GPT + GLM + Kimi + DeepSeek + MiMo via relay) |
| prompt-engineer         | ✱ | ✱ | local — Prompt writing per-vendor best practices |
| recall                  | ✱ | — | local — Search this project's past Claude sessions for an earlier user statement/decision (Claude-only; lexical BM25 over the transcript store) |
| relay                   | ✱ | — | local — Cross-agent relay from Claude to GPT/GLM/Kimi/DeepSeek/MiMo (Claude-only caller) |
| todo                    | ✱ | ✱ | local — TODO.md tracking across sessions |

> Note: SKILL.md supports an optional Claude-only `effort` frontmatter (`medium` / `high` / `max`) to set thinking budget per skill. Currently unset on every skill in this repo — they all inherit the session default.

[c-pdf-a]: https://github.com/anthropics/skills
[c-pdf-o]: https://github.com/openai/skills
[c-sc]: https://github.com/anthropics/skills

### Discovery quirks (not managed here)

- **Plugin-provided skills**: Some skills (e.g., `code-simplifier`) come from Claude marketplace plugins and live in `~/.claude/skills/` as regular directories, not symlinks.

## MCP Servers

| Server | Purpose | Agents |
|--------|---------|--------|
| chrome-devtools | Chrome DevTools bridge for browser automation | Codex |
| codex | Codex MCP server for cross-agent tool access | Codex |

## Plugins

Managed by the `PLUGINS` table in `dotfiles.sh` — each is installed and enabled at **user scope** on every run (`name|marketplace`):

| Plugin | Marketplace | Purpose |
|--------|-------------|---------|
| code-simplifier | claude-plugins-official | Simplify/refactor changed code |

User scope keeps them available across all projects (vs. per-project pinning, which drifts between machines). Plugin install state lives in `~/.claude/plugins/` and is **not** synced by `dfs` — `./dotfiles.sh` reconciles it on each machine. Other marketplace plugins can still be added ad hoc with `claude plugin install`.
