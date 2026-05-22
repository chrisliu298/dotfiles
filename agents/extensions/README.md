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
- Grok   → `~/.grok/skills/`

Each `SKILL.md` works across all three agents. Claude-specific frontmatter (`allowed-tools`, `user-invocable`, `effort`) is ignored by the others. Agent-specific variants (`relay`, `chatgpt`) use per-agent subdirectories.

Toggle manual skills with `./dotfiles.sh enable/disable <name>`; list status via `./dotfiles.sh skills`. Publish own skills to standalone GitHub repos via `./dotfiles.sh publish`.

### Skill matrix

Columns: **C**laude · Code**x** · **G**rok. Legend: ✓ auto-installed · ✱ manual (opt-in via `enable`) · — not wired to this agent.

> DeepSeek is reached **through** Claude Code via the `ds`/`dsx`/… aliases (see `shell/.functions`), so it inherits the Claude column directly.

| Skill | C | X | G | Default | Source · Description |
|-------|:-:|:-:|:-:|:-------:|----------------------|
| arxiv-reader            | ✓ | ✓ | ✓ | on     | local — Read arxiv via TeX / HF markdown / HTML fallback |
| atomic-push             | ✓ | ✓ | ✓ | on     | local — Split changes into atomic commits, then push |
| [autoresearch][p-ar]    | ✱ | ✱ | ✱ | manual | local + [pub][p-ar] — Karpathy-faithful experiment loop |
| [chatgpt][p-cg]         | ✱ | ✱ | — | manual | local + [pub][p-cg] — Send prompts to ChatGPT via Chrome (per-agent subdirs) |
| [citation-assistant][p-ca] | ✱ | ✱ | ✱ | manual | local + [pub][p-ca] — Add verified citations to LaTeX |
| defuddle                | ✓ | ✓ | ✓ | on     | [kepano/obsidian-skills][c-df] — Clean markdown extraction |
| [deslop][p-ds]          | ✱ | ✱ | ✱ | manual | local + [pub][p-ds] — Strip AI-slop from code changes |
| diagnose                | ✱ | ✱ | ✱ | manual | local — Structured root-cause debugging |
| dump                    | ✱ | ✱ | ✱ | manual | local — Dump session knowledge into Obsidian vault |
| goal-elicit             | ✓ | ✓ | ✓ | on     | local — Multi-round interview → verifiable Goal Contract |
| gpt-pro-relay           | ✓ | ✓ | ✓ | on     | local — SSH to ChatGPT Pro Extended on macmini |
| humanizer               | ✓ | ✓ | — | on     | [blader/humanizer][c-hu] — Remove AI signatures from text |
| [interviewer][p-iv]     | ✱ | ✱ | ✱ | manual | local + [pub][p-iv] — Mock AI/ML technical interviews |
| jina                    | ✓ | ✓ | ✓ | on     | local — Fetch web content / search via Jina AI |
| keep-warm               | ✓ | — | — | on     | local — Cache heartbeat (uses Claude-only scheduling tools) |
| [last-call][p-lc]       | ✱ | ✱ | ✱ | manual | local + [pub][p-lc] — Session-end quality review of all changes |
| [nanorepl][p-nr]        | ✱ | ✱ | ✱ | manual | local + [pub][p-nr] — Karpathy-nano reimplementations |
| pdf                     | ✓ | ✓ | ✓ | on     | [anthropics/skills][c-pdf-a] (Claude) / [openai/skills][c-pdf-o] (others) — PDF read/edit |
| [prism][p-pr]           | ✓ | ✓ | — | on     | local + [pub][p-pr] — Multi-perspective parallel review |
| [prompt-engineer][p-pe] | ✓ | ✓ | ✓ | on     | local + [pub][p-pe] — Prompt writing per-vendor best practices |
| push                    | ✓ | ✓ | ✓ | on     | local — Single-commit push to remote |
| [relay][p-rl]           | ✓ | ✓ | — | on     | local + [pub][p-rl] — Cross-agent relay (Claude ↔ Codex, per-agent subdirs) |
| [rlm][p-rlm]            | ✱ | ✱ | ✱ | manual | local + [pub][p-rlm] — Externalize-and-recurse for data-scale tasks |
| runpodctl               | ✱ | ✱ | ✱ | manual | [runpod/skills][c-rp] — Pod management CLI |
| skill-creator           | ✓ | — | — | on     | [anthropics/skills][c-sc] — Create / edit / benchmark skills |
| subagent-executor       | ✱ | ✱ | ✱ | manual | local — Execute multi-task plans via fresh subagents |
| tdd                     | ✱ | ✱ | ✱ | manual | local — Write failing test before production code |
| todo                    | ✓ | ✓ | ✓ | on     | local — TODO.md tracking across sessions |
| typst                   | ✱ | ✱ | ✱ | manual | local — Idiomatic Typst document authoring |
| update-readme           | ✱ | ✱ | ✱ | manual | local — Create or update repo README.md |
| xurl                    | ✓ | ✓ | ✓ | on     | local — X/Twitter via the `xurl` CLI |

> Note: SKILL.md supports an optional Claude-only `effort` frontmatter (`medium` / `high` / `max`) to set thinking budget per skill. Currently unset on every skill in this repo — they all inherit the session default.

[p-ar]: https://github.com/chrisliu298/autoresearch
[p-cg]: https://github.com/chrisliu298/chatgpt
[p-ca]: https://github.com/chrisliu298/citation-assistant
[p-ds]: https://github.com/chrisliu298/deslop
[p-iv]: https://github.com/chrisliu298/interviewer
[p-lc]: https://github.com/chrisliu298/last-call
[p-nr]: https://github.com/chrisliu298/nanorepl
[p-pr]: https://github.com/chrisliu298/prism
[p-pe]: https://github.com/chrisliu298/prompt-engineer
[p-rl]: https://github.com/chrisliu298/relay
[p-rlm]: https://github.com/chrisliu298/rlm
[c-df]: https://github.com/kepano/obsidian-skills
[c-hu]: https://github.com/blader/humanizer
[c-pdf-a]: https://github.com/anthropics/skills
[c-pdf-o]: https://github.com/openai/skills
[c-rp]: https://github.com/runpod/skills
[c-sc]: https://github.com/anthropics/skills

### Vault-scoped (not in dotfiles)

These live in the Obsidian vault's `_claude/skills/` and are only loaded when working inside that vault:

| Skill | Description |
|-------|-------------|
| [note-gen](https://github.com/chrisliu298/note-gen) | Generate Obsidian notes from source materials |
| [vault-linker](https://github.com/chrisliu298/vault-linker) | Build wikilink connections across vaults |
| obsidian-bases | Create and edit Obsidian Bases (`.base` files) |
| obsidian-cli | Interact with Obsidian vaults via the CLI |

### Project-local

| Skill | Description |
|-------|-------------|
| publish-skill | Publish a local skill to a standalone public GitHub repo (lives in `.claude/skills/`, dotfiles-only) |

### Discovery quirks (not managed here)

- **Grok built-ins**: `~/.grok/skills/` also contains shipped extras (`best-of-n`, `check`, `create-skill`, `docx`, `help`, `pptx`, `xlsx`) that aren't from dotfiles.
- **Claude-fallback discovery**: Grok auto-discovers `~/.claude/skills/` as a lowest-priority source. Skills present there (e.g., `keep-warm`, `skill-creator`) remain visible to it even when not symlinked into `~/.grok/skills/` — they just won't auto-trigger unless the prompt strongly matches.
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
