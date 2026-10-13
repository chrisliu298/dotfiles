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

Host-local third-party skills installed by `npx skills` into `~/.agents/skills/` (e.g. `lark-*`, `merlin-*`) are linked into `~/.claude/skills/` too, since Claude Code does not read that directory (Codex does natively). Hosts without it skip the entry, and repo skills win on name clashes.

A shared/universal `SKILL.md` is written to work across both agents; agent-specific scope is set via explicit `SKILLS` entries in `dotfiles.sh` (e.g., relay and prism are claude-only, so they never reach Codex). Claude-specific frontmatter (`allowed-tools`, `user-invocable`, `effort`) is ignored by Codex.

`agent-team` is auto-installed for Claude and Codex and provides one entrypoint for read-only GPT, Claude, Cursor, Muse and ChatGPT Pro tasks (analysis, research, planning and review), running several backends in parallel. It is self-contained: its session runner and helpers live in `agent-team/scripts/`. Run regression checks with `uv run --with pytest pytest agents/skills/agent-team/tests`.

Toggle manual skills with `./dotfiles.sh enable/disable <name>`; list status via `./dotfiles.sh skills`.

### Skill matrix

Columns: **C**laude · Code**x**. Legend: ✓ auto-installed · ✱ manual (opt-in via `enable`) · — not wired to this agent.

> The Claude-only orchestration skills (relay, prism) stay off Codex. `recall` ships as two harness-specific builds under one name; both default to their own complete history and can search the other agent's complete history on request through a shared entrypoint. Relay and prism are additionally guarded so a dispatched peer can't trigger them.

**Enabled** (✓ auto-installed). Claude gets `pdf` and `skill-creator` from the claude.ai-synced skills (`anthropic-skills:*`), not from this repo.

| Skill | C | X | Source · Description |
|-------|:-:|:-:|----------------------|
| agent-team              | ✓ | ✓ | local — Unified read-only GPT/Claude/Cursor/Muse/Pro tasks; parallel backends, tmux (Pro via gpt-pro relay) |
| arxiv-reader            | ✓ | ✓ | local — Read arxiv via TeX / HF markdown / HTML fallback |
| gpt-pro                 | ✓ | ✓ | local — SSH to ChatGPT Pro Extended on macmini (the `gpt-pro` CLI is on PATH from the Codex copy) |
| pdf                     | — | ✓ | [openai/skills][c-pdf-o] — PDF read/edit (Claude uses the claude.ai-synced `anthropic-skills:pdf`) |
| push                    | ✓ | ✓ | local — Push to remote (auto-picks single vs atomic commits) |
| recall                  | ✓ | ✓ | local — Recall from all past sessions of this agent, or the other agent on request (separate Claude and Codex builds with a shared entrypoint) |

**Disabled** (✱ manual, opt-in via `./dotfiles.sh enable <name>`):

| Skill | C | X | Source · Description |
|-------|:-:|:-:|----------------------|
| prism                   | ✱ | — | local — Multi-perspective parallel review (Claude-only caller; dispatches parallax to GPT via relay) |
| relay                   | ✱ | — | local — Cross-agent relay from Claude to GPT (Claude-only caller) |

> Note: SKILL.md supports an optional Claude-only `effort` frontmatter (`medium` / `high` / `max`) to set thinking budget per skill. Currently unset on every skill in this repo — they all inherit the session default.

[c-pdf-o]: https://github.com/openai/skills

### Discovery quirks (not managed here)

- **Plugin-provided skills**: Skills from Claude marketplace plugins live in `~/.claude/skills/` as regular directories, not symlinks.

## MCP Servers

| Server | Purpose | Agents |
|--------|---------|--------|
| chrome-devtools | Chrome DevTools bridge for browser automation | Codex |
| codex | Codex MCP server for cross-agent tool access | Codex |

## Plugins

Managed by the `PLUGINS` table in `dotfiles.sh` — each is installed and enabled at **user scope** on every run (`name|marketplace`):

None are currently managed (the table is empty).

User scope keeps them available across all projects (vs. per-project pinning, which drifts between machines). Plugin install state lives in `~/.claude/plugins/` and is **not** synced by `dfs` — `./dotfiles.sh` reconciles it on each machine. Other marketplace plugins can still be added ad hoc with `claude plugin install`.
