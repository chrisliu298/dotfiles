# Extensions

Agent extensions managed by `dotfiles.sh`. Three types: **skills**, **MCP servers**, and **plugins**.

| Type | What it does | Managed by |
|------|-------------|------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table |
| Plugin | Bundles commands, agents, hooks, and skills | `scripts/install-plugins.sh` + `claude plugin install` |

## Skills

Most skills use one `SKILL.md` that works in both Claude Code and Codex. Agent-specific variants such as `relay` and `chatgpt` use explicit per-agent subdirectories instead. All own skills live in `agents/extensions/skills/` as the single source of truth. Community/third-party skills are cloned to `~/.cache/skills-src/`. Both are symlinked to `~/.claude/skills/` and `~/.codex/skills/`.

Skills in `MANUAL_SKILLS` are not auto-installed. Toggle with `./dotfiles.sh enable/disable <name>`. List status with `./dotfiles.sh skills`. Project-local skills (e.g., `publish-skill`) live in `.claude/skills/` and are available only in the dotfiles repo.

Published skills are synced to their standalone GitHub repos via `./dotfiles.sh publish`.

### Effort Levels

Each local skill sets an `effort` frontmatter key to control how long the model thinks before responding (Claude Code only — Codex ignores unknown frontmatter). Overrides the session default when the skill is invoked.

| Level | Skills |
|-------|--------|
| **medium** | push, atomic-push, recall, jina, rlm, dump, chatgpt, relay |
| **high** | arxiv-reader, deslop, beautify, last-call, update-readme, prompt-engineer, interviewer, citation-assistant, tdd, debug, typst, humanizer, runpodctl |
| **max** | autoresearch, nanorepl, prism, subagent-executor |

### Published Skills

| Skill | Description |
|-------|-------------|
| [autoresearch](https://github.com/chrisliu298/autoresearch) | Autonomous experiment loop faithful to Karpathy's autoresearch |
| [citation-assistant](https://github.com/chrisliu298/citation-assistant) | Add verified citations to LaTeX papers |
| [deslop](https://github.com/chrisliu298/deslop) | Remove AI-generated slop from code changes |
| [interviewer](https://github.com/chrisliu298/interviewer) | Mock technical interviews for AI/ML |
| [last-call](https://github.com/chrisliu298/last-call) | Session-end quality review of all changes |
| [nanorepl](https://github.com/chrisliu298/nanorepl) | Minimal reimplementations following Karpathy's nano philosophy |
| [prism](https://github.com/chrisliu298/prism) | Multi-perspective review through parallel agent deliberation |
| [prompt-engineer](https://github.com/chrisliu298/prompt-engineer) | Write and refine prompts for Claude or Codex |
| [recall](https://github.com/chrisliu298/recall) | Search past sessions and Obsidian notes for context |
| [relay](https://github.com/chrisliu298/relay) | Bidirectional cross-agent relay between Claude Code and Codex |
| [rlm](https://github.com/chrisliu298/rlm) | RLM-inspired externalize-and-recurse for data-scale tasks |
| [chatgpt](https://github.com/chrisliu298/chatgpt) | Send prompts to ChatGPT via Chrome and collect responses (Claude via Claude in Chrome, Codex via chrome-devtools-mcp) |

### Vault-Scoped Skills

These skills live in the Obsidian vault's `_claude/skills/` (not in dotfiles):

| Skill | Description |
|-------|-------------|
| [note-gen](https://github.com/chrisliu298/note-gen) | Generate Obsidian notes from source materials |
| [vault-linker](https://github.com/chrisliu298/vault-linker) | Build wikilink connections across Obsidian vaults |
| obsidian-bases | Create and edit Obsidian Bases (.base files) |
| obsidian-cli | Interact with Obsidian vaults via the CLI |

### Community Skills

| Skill | Source | Agents |
|-------|--------|--------|
| defuddle | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Both |
| humanizer | [blader/humanizer](https://github.com/blader/humanizer) | Both |
| pdf | [anthropics/skills](https://github.com/anthropics/skills) / [openai/skills](https://github.com/openai/skills) | Both |
| runpodctl | [runpod/skills](https://github.com/runpod/skills) | Both |
| skill-creator | [anthropics/skills](https://github.com/anthropics/skills) | Claude |

### Workflow Skills (Local)

| Skill | Description |
|-------|-------------|
| arxiv-reader | Read arxiv papers via TeX source, HF markdown, or HTML fallback |
| atomic-push | Atomic commits and push to remote |
| beautify | Simplify and beautify code changes on the current branch |
| debug | Structured debugging: investigate root cause before proposing fixes |
| dump | Dump session-derived knowledge to Obsidian vault |
| jina | Fetch web content and search via Jina AI (r.jina.ai / s.jina.ai) |
| push | Single-commit push to remote |
| subagent-executor | Execute multi-task plans via fresh subagents with review gates |
| tdd | Test-driven development: write failing test before production code |
| typst | Write Typst documents correctly and idiomatically |
| update-readme | Update or create README.md for repos |

### Project-Local Skills

| Skill | Description |
|-------|-------------|
| publish-skill | Publish local skill to standalone public GitHub repo (dotfiles only) |

## MCP Servers

| Server | Purpose | Agents |
|--------|---------|--------|
| playwright | Headless Chromium for JS-rendered pages | Both |
| codex | Codex MCP server for cross-agent tool access | Claude |

## Plugins

Cloned from GitHub via `PLUGINS` table in `scripts/install-plugins.sh`, installed with `claude plugin install`.

| Plugin | Description |
|--------|-------------|
| [nanoresearch](https://github.com/chrisliu298/nanoresearch) | Autonomous research pipeline (idea discovery, experiments, paper writing) |
| [multi-autoresearch](https://github.com/chrisliu298/multi-autoresearch) | Parallel experiments via worktrees, multi-perspective ideation when stuck |

Marketplace plugins (installed manually, not tracked in `dotfiles.sh`): claude-md-management, pr-review-toolkit, feature-dev, frontend-design, playground, plugin-dev, pyright-lsp.
