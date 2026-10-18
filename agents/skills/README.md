# Skills

This directory (`agents/skills/`) is the single source of truth for repo-owned **skills**, and their **authoring references** (`references/`) — no MCP or plugin config lives here. It doubles as the catalog for all agent extensions across Claude, Codex, Muse Code, and DeepSeek Harness: **skills**, **MCP servers**, and a curated set of **plugins** are all managed by `dotfiles.sh`, but only skills are stored under this path — MCP servers and plugins are defined by the `MCP_SERVERS` and `PLUGINS` tables in `dotfiles.sh`, not here.

| Type | What it does | Managed by |
|------|--------------|------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table in `dotfiles.sh` |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table in `dotfiles.sh` |
| Plugin | Bundles commands, agents, hooks, and skills | `PLUGINS` table in `dotfiles.sh` (user scope) |

## Skills

Single source of truth: own skills live in `agents/skills/`; community/third-party skills are cloned to `~/.cache/skills-src/`. Claude, Codex, and DeepSeek Harness get live symlinks; Muse's managed personal root is owned by its skills store (copy + provenance, so `skills update`/`uninstall` work), so Muse gets reconciled copy-installs instead of symlinks:

- Claude            → `~/.claude/skills/` (symlink)
- Codex             → `~/.codex/skills/` (symlink)
- DeepSeek Harness  → `~/.dsh/skills/` (symlink; `$DSH_HOME/skills` when `DSH_HOME` is set. Only on hosts where the harness has run, i.e. its home directory exists — otherwise the column is skipped so no `~/.dsh` is seeded)
- Muse Code         → `~/.config/muse/skills/` (via `muse skills install` on every run that passes the fingerprint gate; edits therefore reach Muse on the next `./dotfiles.sh`, not live; hosts without the `muse` CLI skip its column)

Repo-sourced Muse installs that the table no longer selects are uninstalled again; skills a user installed into Muse from anywhere else are never touched. Only symlinks are pruned in the three symlink roots, so a hand-installed skill directory survives. Verify the wiring offline (temp `$HOME`, stubbed `muse`) with `./test-dotfiles-muse-skills.sh` and `./test-dotfiles-dsh-skills.sh`.

Host-local third-party skills installed into `~/.agents/skills/` are read natively by Codex, Muse, and DeepSeek Harness (which scans `~/.agents/skills` as a default root); Claude Code does not read that directory. The Claude-only ones (`CLAUDE_ONLY_AGENT_SKILLS` in `dotfiles.sh`: `weekly-report` and `merlin-*`) are moved from there into `~/.claude/skills/` on every run, so only Claude sees them; an existing `~/.claude/skills/<name>` directory is never overwritten. Install new Merlin skills with `merlin-cli skill install <name> --agent claude-code`, which targets `~/.claude/skills/` directly.

A shared/universal `SKILL.md` is written to work across agents; agent-specific scope is set via explicit `SKILLS` entries in `dotfiles.sh` (e.g., agent-team and codex-exec are claude-only, so they never reach Codex or Muse). Muse also discovers `~/.claude/skills` and `~/.codex/skills` natively, so `dotfiles.sh` turns off in Muse every skill found there that the table does not select for Muse. Claude-specific frontmatter (`allowed-tools`, `user-invocable`, `effort`) is ignored by Codex and DeepSeek Harness; Muse records `allowed-tools` as advisory metadata only.

`agent-team` is auto-installed for Claude only and provides one entrypoint for read-only GPT, Claude, Gemini (Cursor Agent), Muse, DeepSeek (Claude Code) and ChatGPT Pro tasks (analysis, research, planning and review), running several backends in parallel. It is self-contained: its session runner and helpers live in `agent-team/scripts/`. Run regression checks with `uv run --with pytest pytest agents/skills/agent-team/tests`.

### Skill matrix

Columns: **C**laude · Code**x** · **M**use · **D**eepSeek Harness. Legend: ✓ installed · — not wired to this agent.

> The Claude-only skills (codex-exec, agent-team, gpt-pro, the three `lark-*`, and the host-local `weekly-report` and `merlin-*`) stay off Codex, Muse and DeepSeek. `recall` ships as two harness-specific builds (Claude, Codex) under one name; each defaults to its own complete history and can search the other agent's complete history on request through a shared entrypoint. It has no Muse or DeepSeek build, so Muse and `~/.dsh/sessions` history isn't searched; `dotfiles.sh` also turns off the Claude/Codex copies Muse discovers natively.

Claude has no `pdf` skill: `agents/claude/settings.json` turns off the claude.ai-synced skills (`syncClaudeAiSkills: false`) and the built-in skills it never uses (`skillOverrides`).

| Skill | C | X | M | D | Source · Description |
|-------|:-:|:-:|:-:|:-:|----------------------|
| agent-team              | ✓ | — | — | — | local — Unified read-only GPT/Claude/Gemini/Muse/DeepSeek/Pro tasks; parallel backends, tmux (Pro via gpt-pro relay) |
| arxiv-reader            | ✓ | ✓ | ✓ | ✓ | local — Read arxiv via TeX / HF markdown / HTML fallback |
| gpt-pro                 | ✓ | — | — | — | local — ChatGPT Pro Extended through the local relay engine (the `gpt-pro` CLI is on PATH from the Claude copy) |
| lark-shared, lark-doc, lark-sheets | ✓ | — | — | — | [larksuite/cli][c-lark] — Feishu auth, docs and sheets through `lark-cli` (`npm install -g @larksuite/cli`); tracks main on every run |
| pdf                     | — | ✓ | — | — | [openai/skills][c-pdf-o] — PDF read/edit (OpenAI's native skill, not repo-owned, so Muse gets no managed copy) |
| recall                  | ✓ | ✓ | — | — | local — Recall from all past sessions of this agent, or the other agent on request (separate Claude and Codex builds with a shared entrypoint; no Muse or DeepSeek build) |

> Note: SKILL.md supports an optional Claude-only `effort` frontmatter (`medium` / `high` / `max`) to set thinking budget per skill. Currently unset on every skill in this repo — they all inherit the session default.

[c-pdf-o]: https://github.com/openai/skills
[c-lark]: https://github.com/larksuite/cli/tree/main/skills

### Discovery quirks (not managed here)

- **Plugin-provided skills**: Skills from Claude marketplace plugins live in `~/.claude/skills/` as regular directories, not symlinks.
- **DeepSeek bundled skills**: DeepSeek Harness also discovers the `office*` skills shipped inside the app, so they appear in its catalog without any repo wiring.

## MCP Servers

| Server | Purpose | Agents |
|--------|---------|--------|
| chrome-devtools | Chrome DevTools bridge for browser automation | Codex |

## Plugins

Managed by the `PLUGINS` table in `dotfiles.sh` — each is installed and enabled at **user scope** on every run (`name|marketplace`):

None are currently managed (the table is empty).

User scope keeps them available across all projects (vs. per-project pinning, which drifts between machines). Plugin install state lives in `~/.claude/plugins/` and is **not** synced by `dfs` — `./dotfiles.sh` reconciles it on each machine. Other marketplace plugins can still be added ad hoc with `claude plugin install`.
