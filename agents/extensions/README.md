# Extensions

Agent extensions for Claude, Codex, and Grok. **Skills**, **MCP servers**, and a curated set of **plugins** are managed by `dotfiles.sh`.

| Type | What it does | Managed by |
|------|--------------|------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table in `dotfiles.sh` |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table in `dotfiles.sh` |
| Plugin | Bundles commands, agents, hooks, and skills | `PLUGINS` table in `dotfiles.sh` (user scope) |

## Skills

Single source of truth: own skills live in `agents/extensions/skills/`; community/third-party skills are cloned to `~/.cache/skills-src/`. Both are symlinked into per-agent skill dirs:

- Claude → `~/.claude/skills/`
- Codex  → `~/.codex/skills/`
- Grok   → `~/.grok/skills/` (relay/prism dispatch target; mirrors the Codex set)

Each `SKILL.md` works across all three agents. Claude-specific frontmatter (`allowed-tools`, `user-invocable`, `effort`) is ignored by Codex and Grok. Per-agent scope is set via explicit `SKILLS` entries in `dotfiles.sh` (e.g., relay and prism are claude-only).

Toggle manual skills with `./dotfiles.sh enable/disable <name>`; list status via `./dotfiles.sh skills`.

### Skill matrix

Columns: **C**laude · Code**x** · **G**rok. Legend: ✓ auto-installed · ✱ manual (opt-in via `enable`) · — not wired to this agent.

> DeepSeek and MiMo are reached **through** Claude Code via the `ds`/`mm`/… aliases (see `shell/.functions`), so they inherit the Claude column directly (no separate skill dir). **Grok** is a relay/prism dispatch target (no interactive alias) with its own `~/.grok/skills/` mirror of the Codex set — so its column equals Code**x**. The Claude-only orchestration skills (relay, prism, goal-loop, keep-warm, skill-creator) stay off Codex/Grok; relay and prism are additionally guarded so a dispatched peer can't trigger them.

| Skill | C | X | G | Default | Source · Description |
|-------|:-:|:-:|:-:|:-------:|----------------------|
| arxiv-reader            | ✓ | ✓ | ✓ | on     | local — Read arxiv via TeX / HF markdown / HTML fallback |
| autoresearch            | ✱ | ✱ | ✱ | manual | local — Karpathy-faithful experiment loop |
| defuddle                | ✓ | ✓ | ✓ | on     | [kepano/obsidian-skills][c-df] — Clean markdown extraction |
| deslop                  | ✓ | ✓ | ✓ | on     | local — Strip AI-slop from code changes |
| digest                  | ✓ | ✓ | ✓ | on     | local — Re-layer a dense reply into a fast-to-skim form |
| goal-drive              | ✓ | ✓ | ✓ | on     | local — Drive a goal artifact (GOAL.md / checklist / phased doc) to verified done |
| goal-elicit             | ✓ | ✓ | ✓ | on     | local — Multi-round interview → verifiable Goal Contract |
| goal-loop               | ✓ | — | — | on     | local — Stepped elicit→review→fix loop (composes goal-elicit/goal-drive/prism; default review is prism, Claude-only) |
| gpt-pro-relay           | ✓ | ✓ | ✓ | on     | local — SSH to ChatGPT Pro Extended on macmini |
| humanizer               | ✓ | ✓ | ✓ | on     | [blader/humanizer][c-hu] — Remove AI signatures from text |
| interviewer             | ✱ | ✱ | ✱ | manual | local — Mock AI/ML technical interviews |
| jina                    | ✓ | ✓ | ✓ | on     | local — Fetch web content / search via Jina AI |
| keep-warm               | ✓ | — | — | on     | local — Cache heartbeat (uses Claude-only scheduling tools) |
| pdf                     | ✓ | ✓ | ✓ | on     | [anthropics/skills][c-pdf-a] (Claude) / [openai/skills][c-pdf-o] (Codex/Grok) — PDF read/edit |
| prism                   | ✓ | — | — | on     | local — Multi-perspective parallel review (Claude-only caller; dispatches parallax to Codex + DeepSeek + MiMo + Grok via relay) |
| prompt-engineer         | ✓ | ✓ | ✓ | on     | local — Prompt writing per-vendor best practices |
| push                    | ✓ | ✓ | ✓ | on     | local — Push to remote (auto-picks single vs atomic commits) |
| rehydrate               | ✓ | ✓ | ✓ | on     | local — Recover post-compaction detail from the raw session transcript |
| relay                   | ✓ | — | — | on     | local — Cross-agent relay from Claude to Codex/DeepSeek/MiMo/Grok (Claude-only caller) |
| skill-creator           | ✓ | — | — | on     | [anthropics/skills][c-sc] — Create / edit / benchmark skills |
| todo                    | ✓ | ✓ | ✓ | on     | local — TODO.md tracking across sessions |
| xurl                    | ✓ | ✓ | ✓ | on     | local — X/Twitter via the `xurl` CLI |

> Note: SKILL.md supports an optional Claude-only `effort` frontmatter (`medium` / `high` / `max`) to set thinking budget per skill. Currently unset on every skill in this repo — they all inherit the session default.

[c-df]: https://github.com/kepano/obsidian-skills
[c-hu]: https://github.com/blader/humanizer
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
