# Extensions

Agent extensions managed by `dotfiles.sh`. Three types: **skills**, **MCP servers**, and **plugins**.

| Type | What it does | Managed by |
|------|--------------|------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table in `dotfiles.sh` |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table in `dotfiles.sh` |
| Plugin | Bundles commands, agents, hooks, and skills | `scripts/install-plugins.sh` + `claude plugin install` |

## Skills

Single source of truth: own skills live in `agents/extensions/skills/`; community/third-party skills are cloned to `~/.cache/skills-src/`. Both are symlinked into per-agent skill dirs:

- Claude → `~/.claude/skills/`
- Codex  → `~/.codex/skills/`

Each `SKILL.md` works across both agents. Claude-specific frontmatter (`allowed-tools`, `user-invocable`, `effort`) is ignored by Codex. Per-agent scope is set via explicit `SKILLS` entries in `dotfiles.sh` (e.g., relay is claude-only).

Toggle manual skills with `./dotfiles.sh enable/disable <name>`; list status via `./dotfiles.sh skills`. Publish own skills to standalone GitHub repos via `./dotfiles.sh publish`.

### Skill matrix

Columns: **C**laude · Code**x**. Legend: ✓ auto-installed · ✱ manual (opt-in via `enable`) · — not wired to this agent.

> DeepSeek and MiMo are reached **through** Claude Code via the `ds`/`mm`/… aliases (see `shell/.functions`), so they inherit the Claude column directly.

| Skill | C | X | Default | Source · Description |
|-------|:-:|:-:|:-------:|----------------------|
| arxiv-reader            | ✓ | ✓ | on     | local — Read arxiv via TeX / HF markdown / HTML fallback |
| [autoresearch][p-ar]    | ✱ | ✱ | manual | local + [pub][p-ar] — Karpathy-faithful experiment loop |
| defuddle                | ✓ | ✓ | on     | [kepano/obsidian-skills][c-df] — Clean markdown extraction |
| [deslop][p-ds]          | ✓ | ✓ | on     | local + [pub][p-ds] — Strip AI-slop from code changes |
| goal-elicit             | ✓ | ✓ | on     | local — Multi-round interview → verifiable Goal Contract |
| gpt-pro-relay           | ✓ | ✓ | on     | local — SSH to ChatGPT Pro Extended on macmini |
| humanizer               | ✓ | ✓ | on     | [blader/humanizer][c-hu] — Remove AI signatures from text |
| [interviewer][p-iv]     | ✱ | ✱ | manual | local + [pub][p-iv] — Mock AI/ML technical interviews |
| jina                    | ✓ | ✓ | on     | local — Fetch web content / search via Jina AI |
| keep-warm               | ✓ | — | on     | local — Cache heartbeat (uses Claude-only scheduling tools) |
| pdf                     | ✓ | ✓ | on     | [anthropics/skills][c-pdf-a] (Claude) / [openai/skills][c-pdf-o] (Codex) — PDF read/edit |
| [prism][p-pr]           | ✓ | — | on     | local + [pub][p-pr] — Multi-perspective parallel review (Claude-only caller; dispatches parallax to Codex + DeepSeek + MiMo via relay) |
| [prompt-engineer][p-pe] | ✓ | ✓ | on     | local + [pub][p-pe] — Prompt writing per-vendor best practices |
| push                    | ✓ | ✓ | on     | local — Push to remote (auto-picks single vs atomic commits) |
| [relay][p-rl]           | ✓ | — | on     | local + [pub][p-rl] — Cross-agent relay from Claude to Codex/DeepSeek/MiMo (Claude-only caller) |
| skill-creator           | ✓ | — | on     | [anthropics/skills][c-sc] — Create / edit / benchmark skills |
| todo                    | ✓ | ✓ | on     | local — TODO.md tracking across sessions |
| xurl                    | ✓ | ✓ | on     | local — X/Twitter via the `xurl` CLI |

> Note: SKILL.md supports an optional Claude-only `effort` frontmatter (`medium` / `high` / `max`) to set thinking budget per skill. Currently unset on every skill in this repo — they all inherit the session default.

[p-ar]: https://github.com/chrisliu298/autoresearch
[p-ds]: https://github.com/chrisliu298/deslop
[p-iv]: https://github.com/chrisliu298/interviewer
[p-pr]: https://github.com/chrisliu298/prism
[p-pe]: https://github.com/chrisliu298/prompt-engineer
[p-rl]: https://github.com/chrisliu298/relay
[c-df]: https://github.com/kepano/obsidian-skills
[c-hu]: https://github.com/blader/humanizer
[c-pdf-a]: https://github.com/anthropics/skills
[c-pdf-o]: https://github.com/openai/skills
[c-sc]: https://github.com/anthropics/skills

### Project-local

| Skill | Description |
|-------|-------------|
| publish-skill | Publish a local skill to a standalone public GitHub repo (lives in `.claude/skills/`, dotfiles-only) |

### Discovery quirks (not managed here)

- **Plugin-provided skills**: Some skills (e.g., `lecture-refine`) come from Claude marketplace plugins and live in `~/.claude/skills/` as regular directories, not symlinks.

## MCP Servers

| Server | Purpose | Agents |
|--------|---------|--------|
| chrome-devtools | Chrome DevTools bridge for browser automation | Codex |
| codex | Codex MCP server for cross-agent tool access | Codex |

## Plugins

Cloned from GitHub via the `PLUGINS` table in `scripts/install-plugins.sh`, installed with `claude plugin install`.

| Plugin | Description | Status |
|--------|-------------|--------|
| [humanize](https://github.com/chrisliu298/humanize) | RLCR loop fork: Claude implements, Codex reviews; ask-gpt-pro consult via gpt-pro-relay | enabled |

Marketplace plugins (installed manually, not tracked in `dotfiles.sh`): claude-md-management, code-review, pr-review-toolkit, feature-dev, frontend-design, pyright-lsp.
