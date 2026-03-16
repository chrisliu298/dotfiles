# Extensions

Agent extensions managed by `dotfiles.sh`. Three types: **skills**, **MCP servers**, and **plugins**.

| Type | What it does | Managed by | Install location |
|------|-------------|------------|------------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table | `~/.claude/skills/`, `~/.codex/skills/` |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table | Registered per-agent (`claude mcp`, `codex mcp`) |
| Plugin | Bundles commands, agents, hooks, and skills | `PLUGINS` table + `claude plugin install` | `~/.claude/plugins/` |

## Skills

Each skill has one SKILL.md that works in both Claude Code and Codex. `dotfiles.sh` clones upstream repos to a cache and creates direct symlinks.

```text
dotfiles/agents/extensions/skills/atomic-push/SKILL.md  # Local skill (in git)
        ↓ symlink
~/.claude/skills/atomic-push/                  # Claude Code reads from here
~/.codex/skills/atomic-push/                   # Codex reads from here

~/.cache/skills-src/anthropics__skills/        # Cloned upstream repo
        ↓ symlink (to subpath)
~/.claude/skills/pdf/                          # Claude Code reads from here
```

- **Local extensions** are symlinked directly from `agents/extensions/skills/` — edits take effect immediately
- **Upstream skills** are cloned to `~/.cache/skills-src/` and symlinked from there; re-run `./dotfiles.sh` to update
- **Agent-specific skills** (`pdf`, `relay`) use separate SKILLS table entries with different sources per agent
- **Repos are cloned in parallel** for speed

### SKILLS Table Format

```bash
# name|source|agents
SKILLS=(
    "*|./agents/extensions/skills|claude,codex"                      # local wildcard
    "defuddle|kepano/obsidian-skills/skills/defuddle|claude,codex"  # upstream
    "pdf|anthropics/skills/skills/pdf|claude"                       # claude-only
    "pdf|openai/skills/skills/.curated/pdf|codex"                   # codex-only (different source)
)
```

### Published Skills

Skills built and maintained as open-source repos.

| Skill | Source | Description | Enhanced |
|-------|--------|-------------|----------|
| autoresearch | [chrisliu298/autoresearch](https://github.com/chrisliu298/autoresearch) | Autonomous experiment loop faithful to Karpathy's autoresearch | |
| citation-assistant | [chrisliu298/citation-assistant](https://github.com/chrisliu298/citation-assistant) | Add verified citations to LaTeX papers | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| deslop | [chrisliu298/deslop](https://github.com/chrisliu298/deslop) | Remove AI-generated slop from code changes | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| interviewer | [chrisliu298/interviewer](https://github.com/chrisliu298/interviewer) | Mock technical interviews for AI/ML | |
| last-call | [chrisliu298/last-call](https://github.com/chrisliu298/last-call) | Session-end quality review of all changes | |
| lbreview | [chrisliu298/lbreview](https://github.com/chrisliu298/lbreview) | Thorough code review of changes against main | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| nanorepl | [chrisliu298/nanorepl](https://github.com/chrisliu298/nanorepl) | Minimal reimplementations following Karpathy's nano philosophy | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| note-gen | [chrisliu298/note-gen](https://github.com/chrisliu298/note-gen) | Generate Obsidian notes from source materials | |
| prism | [chrisliu298/prism](https://github.com/chrisliu298/prism) | Multi-perspective review through parallel agent deliberation | |
| prompt-engineer | [chrisliu298/prompt-engineer](https://github.com/chrisliu298/prompt-engineer) | Write and refine prompts for Claude or GPT/Codex | |
| recall | [chrisliu298/recall](https://github.com/chrisliu298/recall) | Search past sessions and Obsidian notes for context | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| relay | [chrisliu298/relay](https://github.com/chrisliu298/relay) | Bidirectional cross-agent relay between Claude Code and Codex | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| vault-linker | [chrisliu298/vault-linker](https://github.com/chrisliu298/vault-linker) | Build wikilink connections across Obsidian vaults | |

### Community Skills

Public skills by others.

| Skill | Source | Description | Agents |
|-------|--------|-------------|--------|
| defuddle | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Extract clean markdown from web pages via CLI | Both |
| humanizer | [blader/humanizer](https://github.com/blader/humanizer) | Remove AI-generated writing patterns | Both |
| obsidian-cli | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Interact with Obsidian vaults via CLI | Both |
| pdf | [anthropics/skills](https://github.com/anthropics/skills) / [openai/skills](https://github.com/openai/skills) | PDF manipulation: extract, create, merge, split, fill forms | Both |
| skill-creator | [anthropics/skills](https://github.com/anthropics/skills) | Guide for creating new skills | Claude |

### Workflow Skills

Local skills for workflow acceleration, not published as standalone repos.

| Skill | Description | Enhanced |
|-------|-------------|----------|
| atomic-push | Atomic commits and push to remote | |
| publish-skill | Publish local skill to standalone public GitHub repo | |
| push | Single-commit push to remote | |
| session-recovery | Recover sessions after directory rename/move | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| sync-upstream | Sync forked repo with upstream remote | |
| update-readme | Update or create README.md for repos | |

Skills marked with **skill-creator** in the Enhanced column were iteratively refined using the [skill-creator eval framework](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills).

## MCP Servers

Registered per-agent via the `MCP_SERVERS` table in `dotfiles.sh`. Format: `name|command|args`.

| Server | Purpose | Agents | Config |
|--------|---------|--------|--------|
| playwright | Headless Chromium for reading any webpage (JS-rendered, SPAs, guarded sites) | Both | `npx @playwright/mcp@latest --headless --codegen none --console-level error` |
| codex | Codex MCP server for cross-agent tool access | Claude | `codex mcp-server` |

## Plugins

Cloned from GitHub via the `PLUGINS` table, installed with `claude plugin install`. Plugins are Claude Code only.

| Plugin | Source | Description |
|--------|--------|-------------|
| aris-lite | [chrisliu298/aris-lite](https://github.com/chrisliu298/aris-lite) | Autonomous research pipeline (idea discovery, experiments, paper writing) |

Plugins from the official marketplace (`claude plugin install <name>`) are installed manually and not tracked in `dotfiles.sh`.

| Plugin | Description |
|--------|-------------|
| claude-md-management | Audit and improve CLAUDE.md files |
| pr-review-toolkit | Multi-agent PR review |
| feature-dev | Guided feature development |
| frontend-design | Production-grade frontend interfaces |
| playground | Interactive HTML playground builder |
| plugin-dev | Plugin creation and development guide |
| pyright-lsp | Python type checking via Pyright |
