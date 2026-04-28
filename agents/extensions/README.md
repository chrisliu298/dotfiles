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
| **high** | arxiv-reader, deslop, last-call, update-readme, prompt-engineer, interviewer, citation-assistant, tdd, diagnose, typst, humanizer, runpodctl |
| **max** | autoresearch, nanorepl, prism, subagent-executor |

### Published Skills

| Skill | Description | Default |
|-------|-------------|---------|
| [autoresearch](https://github.com/chrisliu298/autoresearch) | Autonomous experiment loop faithful to Karpathy's autoresearch | on |
| [citation-assistant](https://github.com/chrisliu298/citation-assistant) | Add verified citations to LaTeX papers | manual |
| [deslop](https://github.com/chrisliu298/deslop) | Remove AI-generated slop from code changes | manual |
| [interviewer](https://github.com/chrisliu298/interviewer) | Mock technical interviews for AI/ML | manual |
| [last-call](https://github.com/chrisliu298/last-call) | Session-end quality review of all changes | on |
| [nanorepl](https://github.com/chrisliu298/nanorepl) | Minimal reimplementations following Karpathy's nano philosophy | manual |
| [prism](https://github.com/chrisliu298/prism) | Multi-perspective review through parallel agent deliberation | on |
| [prompt-engineer](https://github.com/chrisliu298/prompt-engineer) | Write and refine prompts for Claude or Codex | on |
| [recall](https://github.com/chrisliu298/recall) | Search past sessions and Obsidian notes for context | on |
| [relay](https://github.com/chrisliu298/relay) | Bidirectional cross-agent relay between Claude Code and Codex | on |
| [rlm](https://github.com/chrisliu298/rlm) | RLM-inspired externalize-and-recurse for data-scale tasks | manual |
| [chatgpt](https://github.com/chrisliu298/chatgpt) | Send prompts to ChatGPT via Chrome and collect responses | manual |

### Vault-Scoped Skills

These skills live in the Obsidian vault's `_claude/skills/` (not in dotfiles):

| Skill | Description |
|-------|-------------|
| [note-gen](https://github.com/chrisliu298/note-gen) | Generate Obsidian notes from source materials |
| [vault-linker](https://github.com/chrisliu298/vault-linker) | Build wikilink connections across Obsidian vaults |
| obsidian-bases | Create and edit Obsidian Bases (.base files) |
| obsidian-cli | Interact with Obsidian vaults via the CLI |

### Community Skills

| Skill | Source | Agents | Default |
|-------|--------|--------|---------|
| defuddle | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Both | on |
| humanizer | [blader/humanizer](https://github.com/blader/humanizer) | Both | manual |
| pdf | [anthropics/skills](https://github.com/anthropics/skills) / [openai/skills](https://github.com/openai/skills) | Both | on |
| runpodctl | [runpod/skills](https://github.com/runpod/skills) | Both | manual |
| skill-creator | [anthropics/skills](https://github.com/anthropics/skills) | Claude | on |

### Workflow Skills (Local)

| Skill | Description | Default |
|-------|-------------|---------|
| arxiv-reader | Read arxiv papers via TeX source, HF markdown, or HTML fallback | on |
| atomic-push | Atomic commits and push to remote | on |
| diagnose | Structured debugging: investigate root cause before proposing fixes | manual |
| dump | Dump session-derived knowledge to Obsidian vault | manual |
| jina | Fetch web content and search via Jina AI (r.jina.ai / s.jina.ai) | on |
| pro-relay | Send a prompt to ChatGPT Pro Extended on macmini over SSH | manual |
| push | Single-commit push to remote | on |
| subagent-executor | Execute multi-task plans via fresh subagents with review gates | on |
| tdd | Test-driven development: write failing test before production code | on |
| typst | Write Typst documents correctly and idiomatically | on |
| update-readme | Update or create README.md for repos | on |

### Project-Local Skills

| Skill | Description |
|-------|-------------|
| publish-skill | Publish local skill to standalone public GitHub repo (dotfiles only) |

## MCP Servers

| Server | Purpose | Agents |
|--------|---------|--------|
| chrome-devtools | Chrome DevTools bridge for browser automation | Codex |
| codex | Codex MCP server for cross-agent tool access | Codex |

## Plugins

Cloned from GitHub via `PLUGINS` table in `scripts/install-plugins.sh`, installed with `claude plugin install`.

| Plugin | Description | Status |
|--------|-------------|--------|
| [nanoresearch](https://github.com/chrisliu298/nanoresearch) | Autonomous research pipeline (idea discovery, experiments, paper writing) | disabled |
| [multi-autoresearch](https://github.com/chrisliu298/multi-autoresearch) | Parallel experiments via worktrees, multi-perspective ideation when stuck | disabled |

Marketplace plugins (installed manually, not tracked in `dotfiles.sh`): claude-md-management, code-review, pr-review-toolkit, feature-dev, frontend-design, pyright-lsp.
