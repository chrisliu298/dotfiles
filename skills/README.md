# Extensions

Agent extensions managed by `dotfiles.sh`. Three types: **skills**, **MCP servers**, and **plugins**.

| Type | What it does | Managed by | Install location |
|------|-------------|------------|------------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table | `~/.claude/skills/`, `~/.codex/skills/` |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table | Registered per-agent (`claude mcp`, `codex mcp`) |
| Plugin | Bundles commands, agents, hooks, and skills | `PLUGINS` table + `claude plugin install` | `~/.claude/plugins/` |

## Skills

Each skill has one SKILL.md that works in both Claude Code and Codex. `dotfiles.sh` clones upstream repos to a cache and creates direct symlinks.

```
dotfiles/skills/atomic-push/SKILL.md          # Local skill (in git)
        ↓ symlink
~/.claude/skills/atomic-push/                  # Claude Code reads from here
~/.codex/skills/atomic-push/                   # Codex reads from here

~/.cache/skills-src/anthropics__skills/        # Cloned upstream repo
        ↓ symlink (to subpath)
~/.claude/skills/pdf/                          # Claude Code reads from here
```

- **Local skills** are symlinked directly from `skills/` — edits take effect immediately.
- **Upstream skills** are cloned to `~/.cache/skills-src/` and symlinked from there. Re-run `./dotfiles.sh` to update.
- **Agent-specific skills** (`pdf`, `relay`) use separate SKILLS table entries with different sources per agent.
- **Repos are cloned in parallel** for speed.

### SKILLS table format

```bash
# name|source|agents
SKILLS=(
    "*|./skills|claude,codex"                                    # local wildcard
    "defuddle|kepano/obsidian-skills/skills/defuddle|claude,codex"  # upstream
    "pdf|anthropics/skills/skills/pdf|claude"                    # claude-only
    "pdf|openai/skills/skills/.curated/pdf|codex"                # codex-only (different source)
)
```

### Skill list

| # | Skill | Description | Source | Agents | Enhanced |
|---|-------|-------------|--------|--------|----------|
| 1 | atomic-push | Atomic commits and push to remote | Local | Both | |
| 2 | autoresearch | Autonomous experiment loop faithful to Karpathy's autoresearch | [chrisliu298/autoresearch](https://github.com/chrisliu298/autoresearch) | Both | |
| 3 | citation-assistant | Add verified citations to LaTeX papers | [chrisliu298/citation-assistant](https://github.com/chrisliu298/citation-assistant) | Both | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| 4 | defuddle | Extract clean markdown from web pages via CLI | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Both | |
| 5 | deslop | Remove AI-generated slop from code changes | [chrisliu298/deslop](https://github.com/chrisliu298/deslop) | Both | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| 6 | humanizer | Remove AI-generated writing patterns | [blader/humanizer](https://github.com/blader/humanizer) | Both | |
| 7 | interviewer | Mock technical interviews for AI/ML | [chrisliu298/interviewer](https://github.com/chrisliu298/interviewer) | Both | |
| 8 | last-call | Session-end quality review of all changes | [chrisliu298/last-call](https://github.com/chrisliu298/last-call) | Both | |
| 9 | lbreview | Thorough code review of changes against main | [chrisliu298/lbreview](https://github.com/chrisliu298/lbreview) | Both | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| 10 | nanorepl | Minimal reimplementations following Karpathy's nano philosophy | [chrisliu298/nanorepl](https://github.com/chrisliu298/nanorepl) | Both | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| 11 | note-gen | Generate Obsidian notes from source materials | [chrisliu298/note-gen](https://github.com/chrisliu298/note-gen) | Both | |
| 12 | obsidian-cli | Interact with Obsidian vaults via CLI | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Both | |
| 13 | pdf | PDF manipulation: extract, create, merge, split, fill forms | [anthropics/skills](https://github.com/anthropics/skills) / [openai/skills](https://github.com/openai/skills) | Both | |
| 14 | prism | Parallel multi-agent deliberation with hard completion gate | [chrisliu298/prism](https://github.com/chrisliu298/prism) | Both | |
| 15 | prompt-engineer | Write and refine prompts for Claude or GPT/Codex | [chrisliu298/prompt-engineer](https://github.com/chrisliu298/prompt-engineer) | Both | |
| 16 | publish-skill | Publish local skill to standalone public GitHub repo | Local | Both | |
| 17 | push | Single-commit push to remote | Local | Both | |
| 18 | recall | Search past sessions and Obsidian notes for context | [chrisliu298/recall](https://github.com/chrisliu298/recall) | Both | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| 19 | relay | Bidirectional cross-agent relay between Claude Code and Codex | [chrisliu298/relay](https://github.com/chrisliu298/relay) | Both | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| 20 | session-recovery | Recover sessions after directory rename/move | Local | Both | [skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) |
| 21 | skill-creator | Guide for creating new skills | [anthropics/skills](https://github.com/anthropics/skills) | Claude | |
| 22 | sync-upstream | Sync forked repo with upstream remote | Local | Both | |
| 23 | update-readme | Update or create README.md for repos | Local | Both | |
| 24 | vault-linker | Build wikilink connections across Obsidian vaults | [chrisliu298/vault-linker](https://github.com/chrisliu298/vault-linker) | Both | |

#### Enhanced column

Skills marked with **skill-creator** were iteratively refined using the [skill-creator eval framework](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills). This means the skill went through eval-driven benchmarking, failure analysis, and targeted iteration.

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

Plugins from the official marketplace (`claude plugin install <name>`) are installed manually and not tracked in `dotfiles.sh`:

| Plugin | Description |
|--------|-------------|
| claude-md-management | Audit and improve CLAUDE.md files |
| pr-review-toolkit | Multi-agent PR review |
| feature-dev | Guided feature development |
| frontend-design | Production-grade frontend interfaces |
| playground | Interactive HTML playground builder |
| plugin-dev | Plugin creation and development guide |
| pyright-lsp | Python type checking via Pyright |
