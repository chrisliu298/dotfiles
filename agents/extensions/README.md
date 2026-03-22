# Extensions

Agent extensions managed by `dotfiles.sh`. Three types: **skills**, **MCP servers**, and **plugins**.

| Type | What it does | Managed by |
|------|-------------|------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table |
| Plugin | Bundles commands, agents, hooks, and skills | `PLUGINS` table + `claude plugin install` |

## Skills

One SKILL.md per skill, works in both Claude Code and Codex. All own skills live in `agents/extensions/skills/` as the single source of truth. Community/third-party skills are cloned to `~/.cache/skills-src/`. Both are symlinked to `~/.claude/skills/` and `~/.codex/skills/`.

Published skills are synced to their standalone GitHub repos via `./dotfiles.sh publish`.

### Effort Levels

Each local skill sets an `effort` frontmatter key to control how long the model thinks before responding (Claude Code only — Codex ignores unknown frontmatter). Overrides the session default when the skill is invoked.

| Level | Skills |
|-------|--------|
| **medium** | push, atomic-push, sync-upstream, publish-skill, session-recovery, recall, jina |
| **high** | deslop, beautify, lbreview, last-call, update-readme, note-gen, vault-linker, prompt-engineer, interviewer, citation-assistant |
| **max** | autoresearch, nanorepl, prism |

### Published Skills

| Skill | Description |
|-------|-------------|
| [autoresearch](https://github.com/chrisliu298/autoresearch) | Autonomous experiment loop faithful to Karpathy's autoresearch |
| [citation-assistant](https://github.com/chrisliu298/citation-assistant) | Add verified citations to LaTeX papers |
| [deslop](https://github.com/chrisliu298/deslop) | Remove AI-generated slop from code changes |
| [interviewer](https://github.com/chrisliu298/interviewer) | Mock technical interviews for AI/ML |
| [last-call](https://github.com/chrisliu298/last-call) | Session-end quality review of all changes |
| [lbreview](https://github.com/chrisliu298/lbreview) | Thorough code review of changes against main |
| [nanorepl](https://github.com/chrisliu298/nanorepl) | Minimal reimplementations following Karpathy's nano philosophy |
| [note-gen](https://github.com/chrisliu298/note-gen) | Generate Obsidian notes from source materials |
| [prism](https://github.com/chrisliu298/prism) | Multi-perspective review through parallel agent deliberation |
| [prompt-engineer](https://github.com/chrisliu298/prompt-engineer) | Write and refine prompts for Claude or Codex |
| [recall](https://github.com/chrisliu298/recall) | Search past sessions and Obsidian notes for context |
| [relay](https://github.com/chrisliu298/relay) | Bidirectional cross-agent relay between Claude Code and Codex |
| [chatgpt](https://github.com/chrisliu298/chatgpt) | Send prompts to ChatGPT via Chrome and collect responses (Claude only) |
| [vault-linker](https://github.com/chrisliu298/vault-linker) | Build wikilink connections across Obsidian vaults |

### Community Skills

| Skill | Source | Agents |
|-------|--------|--------|
| browser-use | [browser-use/browser-use](https://github.com/browser-use/browser-use) | Both |
| defuddle | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Both |
| humanizer | [blader/humanizer](https://github.com/blader/humanizer) | Both |
| obsidian-bases | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Both |
| obsidian-cli | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Both |
| pdf | [anthropics/skills](https://github.com/anthropics/skills) / [openai/skills](https://github.com/openai/skills) | Both |
| runpodctl | [runpod/skills](https://github.com/runpod/skills) | Both |
| skill-creator | [anthropics/skills](https://github.com/anthropics/skills) | Claude |

### Workflow Skills (Local)

| Skill | Description |
|-------|-------------|
| atomic-push | Atomic commits and push to remote |
| beautify | Simplify and beautify code changes on the current branch |
| jina | Fetch web content and search via Jina AI (r.jina.ai / s.jina.ai) |
| publish-skill | Publish local skill to standalone public GitHub repo |
| push | Single-commit push to remote |
| session-recovery | Recover sessions after directory rename/move |
| sync-upstream | Sync forked repo with upstream remote |
| typst | Write Typst documents correctly and idiomatically |
| update-readme | Update or create README.md for repos |

## MCP Servers

| Server | Purpose | Agents |
|--------|---------|--------|
| playwright | Headless Chromium for JS-rendered pages | Both |
| codex | Codex MCP server for cross-agent tool access | Claude |

## Plugins

Cloned from GitHub via `PLUGINS` table, installed with `claude plugin install`. Claude Code only.

| Plugin | Description |
|--------|-------------|
| [nanoresearch](https://github.com/chrisliu298/nanoresearch) | Autonomous research pipeline (idea discovery, experiments, paper writing) |

Marketplace plugins (installed manually, not tracked in `dotfiles.sh`): claude-md-management, pr-review-toolkit, feature-dev, frontend-design, playground, plugin-dev, pyright-lsp.
