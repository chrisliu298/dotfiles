# Skills

This directory (`agents/skills/`) is the single source of truth for repo-owned **skills**, and their **authoring references** (`references/`) — no MCP or plugin config lives here. It doubles as the catalog for all agent extensions across Claude, Codex, and DeepSeek Harness: **skills**, **MCP servers**, and a curated set of **plugins** are all managed by `dotfiles.sh`, but only skills are stored under this path — MCP servers and plugins are defined by the `MCP_SERVERS` and `PLUGINS` tables in `dotfiles.sh`, not here.

| Type | What it does | Managed by |
|------|--------------|------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table in `dotfiles.sh` |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table in `dotfiles.sh` |
| Plugin | Bundles commands, agents, hooks, and skills | `PLUGINS` table in `dotfiles.sh` (Claude user scope); Codex native UI plugins are disabled by `agents/codex/computer-use-config.mjs` |

## Skills

Single source of truth: own skills live in `agents/skills/`; community/third-party skills are cloned to `~/.cache/skills-src/`. Claude, Codex, and DeepSeek Harness get live symlinks:

- Claude            → `~/.claude/skills/` (symlink)
- Codex             → `~/.codex/skills/` (symlink)
- DeepSeek Harness  → `~/.dsh/skills/` (symlink; `$DSH_HOME/skills` when `DSH_HOME` is set. Only on hosts where the harness has run, i.e. its home directory exists — otherwise the column is skipped so no `~/.dsh` is seeded)

Only symlinks are pruned in the three skill roots, so a hand-installed skill directory survives. Verify the DeepSeek wiring offline (temp `$HOME`) with `./test-dotfiles-dsh-skills.sh`.

Host-local third-party skills installed into `~/.agents/skills/` are read natively by Codex and DeepSeek Harness (which scans `~/.agents/skills` as a default root); Claude Code does not read that directory. The Claude-only ones (`CLAUDE_ONLY_AGENT_SKILLS` in `dotfiles.sh`: `weekly-report` and `merlin-*`) are moved from there into `~/.claude/skills/` on every run, so only Claude sees them; an existing `~/.claude/skills/<name>` directory is never overwritten. Install new Merlin skills with `merlin-cli skill install <name> --agent claude-code`, which targets `~/.claude/skills/` directly.

A shared/universal `SKILL.md` is written to work across agents; agent-specific scope is set via explicit `SKILLS` entries in `dotfiles.sh` (e.g., codex-exec is claude-only; agent-team is shared by Claude and Codex). Claude-specific frontmatter (`allowed-tools`, `user-invocable`, `effort`) is ignored by Codex and DeepSeek Harness.

`agent-team` is auto-installed for Claude and Codex and provides one entrypoint for read-only `gpt` (Codex CLI), `claude`, `cursor` (Cursor Agent on Gemini), `ds` (DeepSeek through Claude Code) and `pro` (ChatGPT Pro) tasks (analysis, research, planning and review), running several backends in parallel. It is self-contained: its session runner and helpers live in `agent-team/scripts/`. Run regression checks with `uv run --with pytest pytest agents/skills/agent-team/tests`.

### Skill matrix

Columns: **C**laude · Code**x** · **D**eepSeek Harness. Legend: ✓ installed · — not wired to this agent.

> The Claude-only skills (codex-exec, gpt-pro, and the host-local `weekly-report` and `merlin-*`) stay off Codex and DeepSeek. `recall` ships as two harness-specific builds (Claude, Codex) under one name; both drive one `recall` command (`agents/skills/recall/shared/recall`, linked into `~/.local/bin`), which defaults to the calling agent's complete history and reads the other agent's on request. It has no DeepSeek build, so `~/.dsh/sessions` history isn't searched.

Claude has no `pdf` skill: `agents/claude/settings.json` turns off the claude.ai-synced skills (`syncClaudeAiSkills: false`) and the built-in skills it never uses (`skillOverrides`).

| Skill | C | X | D | Source · Description |
|-------|:-:|:-:|:-:|----------------------|
| agent-team              | ✓ | ✓ | — | local — Unified read-only gpt/claude/cursor/ds/pro tasks; parallel backends, tmux (pro via gpt-pro relay) |
| arxiv-reader            | ✓ | ✓ | ✓ | local — Read arxiv via TeX / HF markdown / HTML fallback |
| gpt-pro                 | ✓ | — | — | local — ChatGPT Pro Extended through the local relay engine (the `gpt-pro` CLI is on PATH from the Claude copy) |
| lark                    | ✓ | ✓ | ✓ | local — The `lark-cli` subset we use (docs fetch/update, sheets, wiki, chat reads); points to `lark-cli skills read` for the rest |
| merlin                  | ✓ | ✓ | ✓ | local — The `merlin-cli job-v2` subset we use (submit, read back, logs, priority, capacity) |
| pdf                     | — | ✓ | — | [openai/skills][c-pdf-o] — PDF read/edit (OpenAI's native skill, not repo-owned) |
| recall                  | ✓ | ✓ | — | local — Read past sessions of this agent, or the other agent on request: messages, commands, tool outputs, subagents (separate Claude and Codex builds over one `recall` command; no DeepSeek build) |

> Note: SKILL.md supports an optional Claude-only `effort` frontmatter (`medium` / `high` / `max`) to set thinking budget per skill. Currently unset on every skill in this repo — they all inherit the session default.

[c-pdf-o]: https://github.com/openai/skills

### Discovery quirks (not managed here)

- **Plugin-provided skills**: Skills from Claude marketplace plugins live in `~/.claude/skills/` as regular directories, not symlinks.
- **DeepSeek bundled skills**: DeepSeek Harness also discovers the `office*` skills shipped inside the app, so they appear in its catalog without any repo wiring.

## MCP Servers

| Server | Purpose | Agents |
|--------|---------|--------|
| codex-computer-use | Shared ChatGPT computer use (desktop apps + Helium through the ChatGPT extension); registered only where the app is installed — see [agents/claude](../claude/README.md#codex-computer-use) | Claude, Codex |

## Plugins

Managed by the `PLUGINS` table in `dotfiles.sh` — each is installed and enabled at **user scope** on every run (`name|marketplace`):

No Claude plugins are currently installed by the table (it is empty). Codex's native UI plugins
are disabled on hosts using the shared Computer Use MCP; see [Codex Computer Use](../claude/README.md#codex-computer-use).

User scope keeps them available across all projects (vs. per-project pinning, which drifts between machines). Plugin install state lives in `~/.claude/plugins/`, outside the repo — `./dotfiles.sh` reconciles it. Other marketplace plugins can still be added ad hoc with `claude plugin install`.
